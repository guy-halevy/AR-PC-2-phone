#pragma once
#include <array>
#include <cstdint>
#include <mutex>
#include "phonexr_projection.hpp"

namespace phonexr {
struct HandSnapshot {
    std::mutex mutex;
    std::array<float,126> points{};
    int count=0;
    uint64_t capture=0;
};
static HandSnapshot handSnapshot;

// GL names belong only to the rendering context. Reset without deleting old-context names.
struct HandRenderer {
    GLuint program=0, vao=0, buffer=0, framebuffer=0;
    bool failed=false;
    void reset() { program=vao=buffer=framebuffer=0; failed=false; }
    void release() {
        if(program)glDeleteProgram(program);
        if(vao)glDeleteVertexArrays(1,&vao);
        if(buffer)glDeleteBuffers(1,&buffer);
        if(framebuffer)glDeleteFramebuffers(1,&framebuffer);
        reset();
    }
    bool initialize() {
        if (program) return true;
        if (failed) return false;
        failed=true;
        const char* vertex="#version 300 es\nlayout(location=0) in vec2 p; void main(){gl_Position=vec4(p,0.,1.);gl_PointSize=5.;}";
        const char* fragment="#version 300 es\nprecision mediump float; out vec4 c; void main(){c=vec4(.2,1.,.8,1.);}";
        GLuint shaders[2]={glCreateShader(GL_VERTEX_SHADER),glCreateShader(GL_FRAGMENT_SHADER)};
        const char* sources[2]={vertex,fragment};
        bool compiled=true;
        for(int i=0;i<2;++i){GLint ok=0;glShaderSource(shaders[i],1,&sources[i],nullptr);glCompileShader(shaders[i]);glGetShaderiv(shaders[i],GL_COMPILE_STATUS,&ok);compiled=compiled&&ok;}
        GLuint candidate=glCreateProgram();
        if(compiled){glAttachShader(candidate,shaders[0]);glAttachShader(candidate,shaders[1]);glLinkProgram(candidate);}
        GLint linked=0;glGetProgramiv(candidate,GL_LINK_STATUS,&linked);
        for(GLuint shader:shaders)glDeleteShader(shader);
        if(!linked){glDeleteProgram(candidate);return false;}
        program=candidate;glGenVertexArrays(1,&vao);glGenBuffers(1,&buffer);glGenFramebuffers(1,&framebuffer);
        failed=false;return true;
    }
};
static HandRenderer handRenderer;

struct HandGlState {
    GLint framebuffer,program,vao,buffer,viewport[4];
    GLfloat lineWidth;
    GLboolean color[4],enabled[8];
    const GLenum flags[8]={GL_DEPTH_TEST,GL_STENCIL_TEST,GL_SCISSOR_TEST,GL_CULL_FACE,GL_BLEND,GL_RASTERIZER_DISCARD,GL_SAMPLE_ALPHA_TO_COVERAGE,GL_SAMPLE_COVERAGE};
    HandGlState(){
        glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING,&framebuffer);glGetIntegerv(GL_CURRENT_PROGRAM,&program);
        glGetIntegerv(GL_VERTEX_ARRAY_BINDING,&vao);glGetIntegerv(GL_ARRAY_BUFFER_BINDING,&buffer);
        glGetIntegerv(GL_VIEWPORT,viewport);glGetFloatv(GL_LINE_WIDTH,&lineWidth);glGetBooleanv(GL_COLOR_WRITEMASK,color);
        for(int i=0;i<8;++i)enabled[i]=glIsEnabled(flags[i]);
    }
    ~HandGlState(){
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER,framebuffer);glUseProgram(program);glBindVertexArray(vao);glBindBuffer(GL_ARRAY_BUFFER,buffer);
        glViewport(viewport[0],viewport[1],viewport[2],viewport[3]);glLineWidth(lineWidth);glColorMask(color[0],color[1],color[2],color[3]);
        for(int i=0;i<8;++i){if(enabled[i])glEnable(flags[i]);else glDisable(flags[i]);}
    }
};
// Called after ALVR has rendered each undistorted eye texture, before Cardboard distortion.
inline void renderHands(GLuint texture,int width,int height,const AlvrPose& pose,const AlvrFov& fov,uint64_t now){
    std::array<float,126> points;
    int count;
    {
        std::lock_guard<std::mutex> lock(handSnapshot.mutex);
        if(!handSnapshot.count || now<handSnapshot.capture || now-handSnapshot.capture>150000000ULL)return;
        points=handSnapshot.points;count=handSnapshot.count;
    }
    if(!texture || width<=0 || height<=0)return;
    const float q[]={pose.orientation.x,pose.orientation.y,pose.orientation.z,pose.orientation.w};
    const float angles[]={fov.left,fov.right,fov.up,fov.down};
    constexpr int edges[21][2]={{0,1},{1,2},{2,3},{3,4},{0,5},{5,6},{6,7},{7,8},{5,9},{9,10},{10,11},{11,12},{9,13},{13,14},{14,15},{15,16},{13,17},{0,17},{17,18},{18,19},{19,20}};
    float lines[168]{},joints[84]{};int lineFloats=0,jointFloats=0;
    for(int hand=0;hand<count;++hand){
        float projected[21][2];bool valid[21];
        for(int i=0;i<21;++i){valid[i]=projectHandPoint(points.data()+hand*63+i*3,pose.position,q,angles,projected[i]);if(valid[i]){joints[jointFloats++]=projected[i][0];joints[jointFloats++]=projected[i][1];}}
        for(const auto& edge:edges)if(valid[edge[0]]&&valid[edge[1]])for(int index:edge){lines[lineFloats++]=projected[index][0];lines[lineFloats++]=projected[index][1];}
    }
    if(!jointFloats)return;
    HandGlState restore;
    if(!handRenderer.initialize())return;
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER,handRenderer.framebuffer);
    glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,texture,0);
    if(glCheckFramebufferStatus(GL_DRAW_FRAMEBUFFER)!=GL_FRAMEBUFFER_COMPLETE)return;
    for(GLenum flag:restore.flags)glDisable(flag);
    glColorMask(GL_TRUE,GL_TRUE,GL_TRUE,GL_TRUE);glViewport(0,0,width,height);glLineWidth(1);
    glUseProgram(handRenderer.program);glBindVertexArray(handRenderer.vao);glBindBuffer(GL_ARRAY_BUFFER,handRenderer.buffer);
    glEnableVertexAttribArray(0);glVertexAttribPointer(0,2,GL_FLOAT,GL_FALSE,0,nullptr);
    glBufferData(GL_ARRAY_BUFFER,lineFloats*sizeof(float),lines,GL_STREAM_DRAW);glDrawArrays(GL_LINES,0,lineFloats/2);
    glBufferData(GL_ARRAY_BUFFER,jointFloats*sizeof(float),joints,GL_STREAM_DRAW);glDrawArrays(GL_POINTS,0,jointFloats/2);
}
}

extern "C" JNIEXPORT void JNICALL Java_viritualisres_phonevr_xr_NativeBridge_publishHands(
    JNIEnv* env,jclass,jlong capture,jfloatArray values){
    std::array<float,126> points{};int length=values?env->GetArrayLength(values):0;
    bool valid=capture>0&&(length==63||length==126);
    if(valid){env->GetFloatArrayRegion(values,0,length,points.data());for(int i=0;i<length;++i)valid=valid&&std::isfinite(points[i])&&std::abs(points[i])<=100;}
    std::lock_guard<std::mutex> lock(phonexr::handSnapshot.mutex);
    phonexr::handSnapshot.count=valid?length/63:0;
    if(valid){phonexr::handSnapshot.points=points;phonexr::handSnapshot.capture=static_cast<uint64_t>(capture);}
}
