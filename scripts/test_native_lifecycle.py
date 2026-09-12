"""Run the prepared native teardown functions against instrumented host stubs."""
import argparse
from pathlib import Path
import subprocess
import tempfile


def body(source, marker):
    start = source.index(marker)
    begin = source.index('{', start)
    depth = 1
    end = begin + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', type=Path, required=True)
    args = parser.parse_args()
    source = (args.project / 'app/src/main/cpp/alvr_main.cpp').read_text()
    stop = body(source, 'void stopInputThread()')
    release = body(source, 'Java_viritualisres_phonevr_ALVRActivity_releaseGlNative(')
    destroy = body(source, 'Java_viritualisres_phonevr_ALVRActivity_destroyNative(')
    harness = r'''
#include <atomic>
#include <cassert>
#include <mutex>
#include <thread>
#define GL(call) call
using jobject = void*;
std::atomic<bool> workerEnded{true};
int deletedRefs=0, glDeletes=0, coreDeletes=0, context=1;
namespace phonexr { struct Renderer { void release() {} }; Renderer handRenderer; }
struct JNIEnv { void DeleteGlobalRef(void*) { ++deletedRefs; } };
struct Context {
 std::atomic<bool> streaming{false}; std::thread inputThread;
 bool running=true,glContextRecreated=false,renderingParamsChanged=false;
 void* headTracker=nullptr; void* lensDistortion=nullptr; void* distortionRenderer=nullptr; void* javaContext=nullptr;
 unsigned lobbyTextures[2]{1,2},streamTextures[2]{3,4};
} CTX;
std::mutex lifecycleMutex;
bool glInitialized=true;
constexpr int EGL_NO_CONTEXT=0;
int eglGetCurrentContext(){return context;}
void alvr_pause_opengl(){ assert(workerEnded); ++glDeletes; }
void alvr_destroy_opengl(){ assert(workerEnded); ++glDeletes; }
void glDeleteTextures(int,const unsigned*){++glDeletes;}
void CardboardDistortionRenderer_destroy(void*){++glDeletes;}
void CardboardHeadTracker_destroy(void*){assert(workerEnded);}
void CardboardLensDistortion_destroy(void*){assert(workerEnded);}
void alvr_destroy(){assert(workerEnded);++coreDeletes;}
'''
    harness += stop + '\nvoid ' + release + '\nvoid ' + destroy
    harness += r'''
void startWorker() {
 workerEnded=false; CTX.streaming=true;
 CTX.inputThread=std::thread([]{ while(CTX.streaming.load()) std::this_thread::yield(); workerEnded=true; });
}
int main(){
 JNIEnv env;
 // Destroy must synchronously stop a live worker even without a STOP event.
 for(int i=0;i<100;i++){
  CTX.javaContext=reinterpret_cast<void*>(1); CTX.headTracker=reinterpret_cast<void*>(1);
  startWorker();
  Java_viritualisres_phonevr_ALVRActivity_destroyNative(&env,nullptr);
  assert(workerEnded && !CTX.inputThread.joinable() && CTX.javaContext==nullptr);
  stopInputThread(); // repeated STOP is harmless
 }
 assert(deletedRefs==100 && coreDeletes==100 && glDeletes==0);
 // A missing EGL context must never run GL destruction on the caller.
 glInitialized=true; context=0;
 Java_viritualisres_phonevr_ALVRActivity_releaseGlNative(&env,nullptr);
 assert(glDeletes==0);
 context=1; CTX.distortionRenderer=reinterpret_cast<void*>(1); startWorker();
 Java_viritualisres_phonevr_ALVRActivity_releaseGlNative(&env,nullptr);
 assert(workerEnded && !CTX.inputThread.joinable() && glDeletes==5 && !glInitialized);
 assert(CTX.lobbyTextures[0]==0 && CTX.streamTextures[1]==0 && CTX.distortionRenderer==nullptr);
 Java_viritualisres_phonevr_ALVRActivity_releaseGlNative(&env,nullptr);
 assert(glDeletes==5);
}
'''
    with tempfile.TemporaryDirectory() as tmp:
        cpp = Path(tmp) / 'lifecycle.cpp'
        binary = Path(tmp) / 'lifecycle'
        cpp.write_text(harness)
        subprocess.run(['c++', '-std=c++17', '-pthread', '-fsanitize=address,undefined', '-g', str(cpp), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True, timeout=20)
    print('Prepared native lifecycle regression passed: 100 live-worker destroys, repeat stop, EGL guard, GL cleanup, JNI references.')


if __name__ == '__main__':
    main()
