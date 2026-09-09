// SPDX-License-Identifier: GPL-3.0-or-later
// PhoneXR integration for Desktop+ v3.6. Runs exclusively on OutputManager's thread.
#include "OutputManager.h"
#include "Overlays.h"
#include "PhoneXRAdapter.h"
#include <windows.h>
#include <shlobj.h>
#include <sddl.h>
#include <aclapi.h>
#include <dwmapi.h>
#include <map>
#include <set>
#include <sstream>
#include <iomanip>
#include <locale>
#include <cmath>
#include <cstdint>
#include <cstring>
#pragma comment(lib, "Advapi32.lib")
#pragma comment(lib, "Shell32.lib")
#pragma comment(lib, "Dwmapi.lib")

namespace {
#pragma pack(push, 1)
struct Command { char magic[4]; uint32_t version; uint64_t session, panel, revision, request; float matrix[16]; float width; };
#pragma pack(pop)
static_assert(sizeof(Command) == 108, "Wire format must match <4sIQQQQ16ff");
struct Entry { uint64_t revision = 0; std::string signature; unsigned int index = 0; bool mutable_panel = false; };
std::map<uint64_t, Entry> entries;
uint64_t sequence = 0, ack = 0, session = 0;
const char* ack_status = "none";
std::wstring directory;
ULONGLONG last_tick = 0;
uint64_t UnixMs() { FILETIME t; GetSystemTimeAsFileTime(&t); ULARGE_INTEGER u; u.LowPart=t.dwLowDateTime; u.HighPart=t.dwHighDateTime; return (u.QuadPart-116444736000000000ULL)/10000; }
bool PlainDirectory(const std::wstring& p) { DWORD a=GetFileAttributesW(p.c_str()); return a!=INVALID_FILE_ATTRIBUTES && (a&FILE_ATTRIBUTE_DIRECTORY) && !(a&FILE_ATTRIBUTE_REPARSE_POINT); }
bool Init() {
    PWSTR local=nullptr;
    if (FAILED(SHGetKnownFolderPath(FOLDERID_LocalAppData, 0, nullptr, &local))) return false;
    std::wstring root(local); CoTaskMemFree(local);
    HANDLE token=nullptr; if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token)) return false;
    DWORD size=0; GetTokenInformation(token, TokenUser, nullptr, 0, &size);
    std::vector<BYTE> info(size);
    bool ok=GetTokenInformation(token, TokenUser, info.data(), size, &size)!=FALSE; CloseHandle(token);
    if (!ok) return false;
    LPWSTR sid=nullptr; if (!ConvertSidToStringSidW(reinterpret_cast<TOKEN_USER*>(info.data())->User.Sid, &sid)) return false;
    std::wstring sddl=L"D:P(A;OICI;FA;;;"+std::wstring(sid)+L")"; LocalFree(sid);
    PSECURITY_DESCRIPTOR sd=nullptr;
    if (!ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl.c_str(), SDDL_REVISION_1, &sd, nullptr)) return false;
    SECURITY_ATTRIBUTES sa={sizeof(sa),sd,FALSE};
    root+=L"\\PhoneXR"; CreateDirectoryW(root.c_str(), &sa);
    ok=PlainDirectory(root);
    directory=root+L"\\DesktopPlus";
    if (ok) { CreateDirectoryW(directory.c_str(), &sa); ok=PlainDirectory(directory); }
    BOOL present=FALSE, defaulted=FALSE; PACL acl=nullptr;
    if (ok) ok=GetSecurityDescriptorDacl(sd,&present,&acl,&defaulted) && present &&
        SetNamedSecurityInfoW(&directory[0],SE_FILE_OBJECT,DACL_SECURITY_INFORMATION|PROTECTED_DACL_SECURITY_INFORMATION,nullptr,nullptr,acl,nullptr)==ERROR_SUCCESS;
    LocalFree(sd);
    if (!ok) { directory.clear(); return false; }
    FILETIME t; GetSystemTimeAsFileTime(&t); session=(uint64_t(t.dwHighDateTime)<<32)|t.dwLowDateTime;
    session^=uint64_t(GetCurrentProcessId());
    return true;
}
bool AtomicWrite(const wchar_t* name, const std::string& data) {
    const std::wstring dest=directory+L"\\"+name, tmp=dest+L".tmp";
    HANDLE h=CreateFileW(tmp.c_str(),GENERIC_WRITE,0,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL|FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
    if (h==INVALID_HANDLE_VALUE) return false;
    DWORD n=0; bool ok=WriteFile(h,data.data(),DWORD(data.size()),&n,nullptr) && n==data.size(); CloseHandle(h);
    if (ok) ok=MoveFileExW(tmp.c_str(),dest.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)!=FALSE;
    if (!ok) DeleteFileW(tmp.c_str()); return ok;
}
bool Rigid(const float* m) {
    for(int i=0;i<16;++i) if(!std::isfinite(m[i])) return false;
    if(std::fabs(m[12])+std::fabs(m[13])+std::fabs(m[14])+std::fabs(m[15]-1)>0.001f) return false;
    for(int a=0;a<3;++a) for(int b=0;b<3;++b) { float dot=0; for(int r=0;r<3;++r) dot+=m[r*4+a]*m[r*4+b]; if(std::fabs(dot-(a==b?1.0f:0.0f))>0.002f) return false; }
    float det=m[0]*(m[5]*m[10]-m[6]*m[9])-m[1]*(m[4]*m[10]-m[6]*m[8])+m[2]*(m[4]*m[9]-m[5]*m[8]);
    return det>0.998f && det<1.002f && std::fabs(m[3])<100 && std::fabs(m[7])<100 && std::fabs(m[11])<100;
}
void Vector(std::ostream& out,const Matrix4& m,int offset) { out<<'['<<m[offset]<<','<<m[offset+1]<<','<<m[offset+2]<<']'; }
std::string Panels(OutputManager& output) {
    auto& manager=OverlayManager::Get(); std::ostringstream all; all.imbue(std::locale::classic()); all<<'[';
    std::set<uint64_t> seen; bool first=true;
    for(unsigned int i=0;i<manager.GetOverlayCount();++i) {
        const auto& overlay=manager.GetOverlay(i); const auto& data=manager.GetConfigData(i);
        uint64_t id=overlay.GetHandle(); if(id==vr::k_ulOverlayHandleInvalid) continue;
        seen.insert(id); auto& e=entries[id]; e.index=i;
        Matrix4 middle=manager.GetOverlayMiddleTransform(i); float rm[16];
        for(int r=0;r<4;++r) for(int c=0;c<4;++c) rm[r*4+c]=middle[c*4+r];
        float width=0; bool valid=Rigid(rm) && vr::VROverlay()->GetOverlayWidthInMeters(id,&width)==vr::VROverlayError_None;
        float height=output.GetOverlayHeight(i); valid=valid && std::isfinite(width) && std::isfinite(height) && width>0 && height>0;
        // Never serialize non-finite JSON, including panels whose runtime transform is unavailable.
        if(!valid) { middle=Matrix4(); width=height=0; }
        const auto& crop=overlay.GetValidatedCropRect();
        int cx=crop.GetTL().x, cy=crop.GetTL().y, cw=crop.GetWidth(), ch=crop.GetHeight();
        int bx=0,by=0,bw=0,bh=0; HWND hwnd=nullptr; UINT dpi=0; bool mapping=false;
        auto source=overlay.GetTextureSource();
        if(source==ovrl_texsource_desktop_duplication && !output.IsOutputInvalid()) {
            bx=output.GetDDPDesktopX(); by=output.GetDDPDesktopY(); bw=output.GetDDPDesktopWidth(); bh=output.GetDDPDesktopHeight(); mapping=true;
        } else if(source==ovrl_texsource_winrt_capture) {
            hwnd=(HWND)data.ConfigHandle[configid_handle_overlay_state_winrt_hwnd];
            int desktop=data.ConfigInt[configid_int_overlay_winrt_desktop_id];
            if(hwnd && desktop==-2 && IsWindow(hwnd) && IsWindowVisible(hwnd) && !IsIconic(hwnd)) {
                RECT bounds={}; DWORD cloaked=1;
                // DWM bounds and WinRT content dimensions are physical pixels. No client-rect scaling.
                if(SUCCEEDED(DwmGetWindowAttribute(hwnd,DWMWA_EXTENDED_FRAME_BOUNDS,&bounds,sizeof(bounds))) &&
                   SUCCEEDED(DwmGetWindowAttribute(hwnd,DWMWA_CLOAKED,&cloaked,sizeof(cloaked))) && !cloaked) {
                    bx=bounds.left; by=bounds.top; bw=bounds.right-bounds.left; bh=bounds.bottom-bounds.top;
                    dpi=GetDpiForWindow(hwnd); mapping=dpi!=0;
                }
            } else if(!hwnd && desktop>=0 && size_t(desktop)<output.GetDesktopRects().size()) {
                const auto& b=output.GetDesktopRects()[desktop]; bx=b.GetTL().x; by=b.GetTL().y; bw=b.GetWidth(); bh=b.GetHeight(); mapping=true;
            }
            // Resizing/asynchronous capture mismatch disables input until content catches up.
            mapping=mapping && bw==data.ConfigInt[configid_int_overlay_state_content_width] && bh==data.ConfigInt[configid_int_overlay_state_content_height];
        }
        mapping=mapping && cw>0 && ch>0 && cx>=0 && cy>=0 && cw<=bw && ch<=bh && cx<=bw-cw && cy<=bh-ch;
        const int origin=data.ConfigInt[configid_int_overlay_origin];
        bool flat=!data.ConfigBool[configid_bool_overlay_3D_enabled] && data.ConfigFloat[configid_float_overlay_curvature]==0;
        bool interactive=valid && mapping && flat && overlay.IsVisible() && overlay.GetOpacity()>0 && data.ConfigBool[configid_bool_overlay_input_enabled] && origin!=ovrl_origin_theater_screen;
        e.mutable_panel=interactive && !data.ConfigBool[configid_bool_overlay_transform_locked] && (origin==ovrl_origin_room || origin==ovrl_origin_seated_universe);
        std::ostringstream p; p.imbue(std::locale::classic()); p<<std::setprecision(9);
        p<<"\"id\":\""<<id<<"\",\"visible\":"<<(overlay.IsVisible()?"true":"false")<<",\"interactive\":"<<(interactive?"true":"false")<<",\"mutable\":"<<(e.mutable_panel?"true":"false")<<",\"hwnd\":\""<<uint64_t(reinterpret_cast<uintptr_t>(hwnd))<<"\",\"center\":"; Vector(p,middle,12);
        p<<",\"right\":"; Vector(p,middle,0); p<<",\"up\":"; Vector(p,middle,4); p<<",\"normal\":"; Vector(p,middle,8);
        p<<",\"widthM\":"<<width<<",\"heightM\":"<<height<<",\"pixelRect\":["<<bx+cx<<','<<by+cy<<','<<cw<<','<<ch<<"],\"crop\":["<<cx<<','<<cy<<','<<cw<<','<<ch<<"],\"captureBounds\":["<<bx<<','<<by<<','<<bw<<','<<bh<<"],\"dpi\":"<<dpi<<",\"origin\":"<<origin<<",\"captureSource\":"<<int(source);
        std::string signature=p.str();
        // Include configuration state even when two offset/pose combinations yield the same world pose.
        std::ostringstream cfg; cfg.imbue(std::locale::classic()); cfg<<std::setprecision(9);
        for(int k=0;k<16;++k) cfg<<data.ConfigTransform[k]<<',';
        cfg<<data.ConfigFloat[configid_float_overlay_offset_right]<<','<<data.ConfigFloat[configid_float_overlay_offset_up]<<','<<data.ConfigFloat[configid_float_overlay_offset_forward];
        std::string complete=signature+cfg.str(); if(e.signature!=complete) { e.signature=complete; ++e.revision; }
        if(!first) all<<','; first=false; all<<'{'<<signature<<",\"revision\":"<<e.revision<<'}';
    }
    // Retain tombstones so a runtime handle reused later cannot reuse an old revision.
    for(auto& item:entries) if(!seen.count(item.first)) { item.second.signature.clear(); item.second.mutable_panel=false; }
    all<<']'; return all.str();
}
}

bool OutputManager::PhoneXRApply(unsigned int index, const float* row_major, float width) {
    auto& manager=OverlayManager::Get(); if(index>=manager.GetOverlayCount() || m_OverlayDragger.IsDragActive() || m_OverlayDragger.IsDragGestureActive()) return false;
    auto& data=manager.GetConfigData(index); auto origin=(OverlayOrigin)data.ConfigInt[configid_int_overlay_origin];
    if((origin!=ovrl_origin_room && origin!=ovrl_origin_seated_universe) || data.ConfigBool[configid_bool_overlay_transform_locked]) return false;
    Matrix4 world; for(int r=0;r<4;++r) for(int c=0;c<4;++c) world[c*4+r]=row_major[r*4+c];
    // Same origin inversion and local-offset removal as OverlayDragger::DragFinish.
    // Room/seated overlays use a center origin and have no dashboard bottom offset.
    Matrix4 base=m_OverlayDragger.GetBaseOffsetMatrix(origin); base.invert();
    Matrix4 relative=base*world;
    relative.translate_relative(-data.ConfigFloat[configid_float_overlay_offset_right],-data.ConfigFloat[configid_float_overlay_offset_up],-data.ConfigFloat[configid_float_overlay_offset_forward]);
    data.ConfigTransform=relative; data.ConfigFloat[configid_float_overlay_width]=width;
    unsigned int previous=manager.GetCurrentOverlayID(); manager.SetCurrentOverlayID(index); ApplySettingTransform(); manager.SetCurrentOverlayID(previous);
    return true;
}
void PhoneXRAdapterTick(OutputManager& output) {
    auto now=GetTickCount64(); if(now-last_tick<33) return; last_tick=now;
    if(directory.empty() && !Init()) return;
    if(!vr::VROverlay()) return;
    std::string panels=Panels(output); // Refresh before revision validation on the owning thread.
    std::wstring incoming=directory+L"\\command.bin", processing=directory+L"\\command.processing";
    if(MoveFileExW(incoming.c_str(),processing.c_str(),MOVEFILE_REPLACE_EXISTING)) {
        Command c={}; HANDLE h=CreateFileW(processing.c_str(),GENERIC_READ,0,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL|FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
        DWORD n=0; LARGE_INTEGER size={}; bool valid=h!=INVALID_HANDLE_VALUE;
        if(valid) {
            FILETIME modified={}; ULARGE_INTEGER stamp={};
            valid=GetFileTime(h,nullptr,nullptr,&modified)!=FALSE;
            stamp.LowPart=modified.dwLowDateTime; stamp.HighPart=modified.dwHighDateTime;
            uint64_t command_ms=stamp.QuadPart>=116444736000000000ULL ? (stamp.QuadPart-116444736000000000ULL)/10000 : 0;
            uint64_t current_ms=UnixMs();
            valid=valid && command_ms<=current_ms+50 && current_ms<=command_ms+500 &&
                GetFileSizeEx(h,&size) && size.QuadPart==sizeof(c) && ReadFile(h,&c,sizeof(c),&n,nullptr) && n==sizeof(c);
            CloseHandle(h);
        }
        DeleteFileW(processing.c_str()); ack_status="invalid";
        if(valid && std::memcmp(c.magic,"PXR1",4)==0 && c.version==1) {
            ack=c.request;
            if(c.session!=session) ack_status="stale";
            else {
                auto it=entries.find(c.panel);
                if(it==entries.end()) ack_status="unavailable";
                else if(it->second.revision!=c.revision) ack_status="stale";
                else if(!it->second.mutable_panel) ack_status="unavailable";
                else if(Rigid(c.matrix) && std::isfinite(c.width) && c.width>=0.10f && c.width<=10.0f) {
                    ack_status=output.PhoneXRApply(it->second.index,c.matrix,c.width)?"accepted":"unavailable";
                    panels=Panels(output);
                }
            }
        }
    }
    std::ostringstream doc; doc.imbue(std::locale::classic());
    doc<<"{\"version\":1,\"sessionId\":\""<<session<<"\",\"sequence\":"<<++sequence<<",\"updatedUnixMs\":"<<UnixMs()<<",\"ackRequestId\":"<<ack<<",\"ackStatus\":\""<<ack_status<<"\",\"panels\":"<<panels<<'}';
    AtomicWrite(L"panels.json",doc.str());
}
