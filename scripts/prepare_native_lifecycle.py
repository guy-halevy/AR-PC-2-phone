"""Checked lifecycle repairs for the pinned PhoneVR Android sources."""
from pathlib import Path


def apply(project):
    project = Path(project)
    cpp = project / 'app/src/main/cpp/alvr_main.cpp'
    java = project / 'app/src/main/java/viritualisres/phonevr/ALVRActivity.java'
    c = cpp.read_text()
    j = java.read_text()
    if '// PhoneXR native lifecycle v1' in c:
        if '// PhoneXR native lifecycle v1' not in j:
            raise RuntimeError('Partial lifecycle patch')
        return

    def replace(old, new):
        nonlocal c
        if c.count(old) != 1:
            raise RuntimeError('Native lifecycle anchor mismatch: ' + old[:100])
        c = c.replace(old, new, 1)

    replace('#include <thread>', '#include <thread>\n#include <atomic>\n#include <mutex>\n#include <EGL/egl.h>\n// PhoneXR native lifecycle v1')
    replace('    bool streaming = false;', '    std::atomic<bool> streaming{false};')
    replace('NativeContext CTX = {};', '''NativeContext CTX = {};
// Lifecycle mutex is never acquired by the input worker: joining cannot deadlock it.
std::mutex lifecycleMutex;
std::mutex viewConfigMutex;
bool glInitialized = false;

void stopInputThread() {
    CTX.streaming.store(false);
    if (CTX.inputThread.joinable()) CTX.inputThread.join();
}
''')
    replace('    AlvrPose headPose = xrPose ? *xrPose : getPose(targetTimestampNs);', '    std::lock_guard<std::mutex> configLock(viewConfigMutex);\n    AlvrPose headPose = xrPose ? *xrPose : getPose(targetTimestampNs);')
    replace('    CTX.javaContext = env->NewGlobalRef(obj);', '    std::lock_guard<std::mutex> lifecycleLock(lifecycleMutex);\n    CTX.javaContext = env->NewGlobalRef(obj);')
    start = c.index('extern "C" JNIEXPORT void JNICALL Java_viritualisres_phonevr_ALVRActivity_destroyNative(')
    end = c.index('extern "C" JNIEXPORT void JNICALL Java_viritualisres_phonevr_ALVRActivity_resumeNative(', start)
    c = c[:start] + '''// Called only by the GLSurfaceView thread, before its EGL context is paused.
extern "C" JNIEXPORT void JNICALL
Java_viritualisres_phonevr_ALVRActivity_releaseGlNative(JNIEnv *, jobject) {
    std::lock_guard<std::mutex> lifecycleLock(lifecycleMutex);
    if (!glInitialized || eglGetCurrentContext() == EGL_NO_CONTEXT) return;
    stopInputThread();
    alvr_pause_opengl();
    alvr_destroy_opengl();
    GL(glDeleteTextures(2, CTX.lobbyTextures));
    GL(glDeleteTextures(2, CTX.streamTextures));
    CTX.lobbyTextures[0] = CTX.lobbyTextures[1] = 0;
    CTX.streamTextures[0] = CTX.streamTextures[1] = 0;
    if (CTX.distortionRenderer) CardboardDistortionRenderer_destroy(CTX.distortionRenderer);
    CTX.distortionRenderer = nullptr;
    glInitialized = false;
    CTX.glContextRecreated = true;
    CTX.renderingParamsChanged = true;
}

extern "C" JNIEXPORT void JNICALL Java_viritualisres_phonevr_ALVRActivity_destroyNative(
    JNIEnv *env, jobject) {
    std::lock_guard<std::mutex> lifecycleLock(lifecycleMutex);
    CTX.running = false;
    stopInputThread();
    alvr_destroy();
    if (CTX.headTracker) CardboardHeadTracker_destroy(CTX.headTracker);
    CTX.headTracker = nullptr;
    if (CTX.lensDistortion) CardboardLensDistortion_destroy(CTX.lensDistortion);
    CTX.lensDistortion = nullptr;
    // Never call a GL destructor from this UI-thread fallback. The context owns
    // any remaining GPU allocation; a timed-out release must not delete new-context names.
    CTX.distortionRenderer = nullptr;
    glInitialized = false;
    if (CTX.javaContext) env->DeleteGlobalRef(CTX.javaContext);
    CTX.javaContext = nullptr;
}

''' + c[end:]
    replace('    CardboardHeadTracker_resume(CTX.headTracker);', '    std::lock_guard<std::mutex> lifecycleLock(lifecycleMutex);\n    CardboardHeadTracker_resume(CTX.headTracker);')
    replace('    alvr_pause();\n\n    if (CTX.running)', '    std::lock_guard<std::mutex> lifecycleLock(lifecycleMutex);\n    stopInputThread();\n    alvr_pause();\n\n    if (CTX.running)')
    replace('    alvr_initialize_opengl();\n    phonexr::handRenderer.reset();\n\n    CTX.glContextRecreated', '    std::lock_guard<std::mutex> lifecycleLock(lifecycleMutex);\n    alvr_initialize_opengl();\n    phonexr::handRenderer.reset();\n    glInitialized = true;\n\n    CTX.glContextRecreated')
    replace('    CTX.screenWidth = width;', '    std::lock_guard<std::mutex> lifecycleLock(lifecycleMutex);\n    CTX.screenWidth = width;')
    replace('    alvr_send_battery(HEAD_ID, level, plugged);', '    std::lock_guard<std::mutex> lifecycleLock(lifecycleMutex);\n    if (CTX.javaContext) alvr_send_battery(HEAD_ID, level, plugged);')
    replace('    try {\n        if (CTX.renderingParamsChanged)', '''    std::lock_guard<std::mutex> lifecycleLock(lifecycleMutex);
    if (!CTX.running) return;
    if (!glInitialized) {
        alvr_initialize_opengl();
        glInitialized = true;
        CTX.glContextRecreated = true;
    }
    try {
        if (CTX.renderingParamsChanged)''')
    replace('            info("renderingParamsChanged, processing new params");', '            std::lock_guard<std::mutex> configLock(viewConfigMutex);\n            info("renderingParamsChanged, processing new params");')
    replace('                CTX.fovArr[0] = getFov((CardboardEye) 0);\n                CTX.fovArr[1] = getFov((CardboardEye) 1);', '''                {
                    std::lock_guard<std::mutex> configLock(viewConfigMutex);
                    CTX.fovArr[0] = getFov((CardboardEye) 0);
                    CTX.fovArr[1] = getFov((CardboardEye) 1);
                }''')
    replace('                CTX.streaming = true;\n                CTX.inputThread = std::thread(inputThread);', '                stopInputThread();\n                CTX.streaming = true;\n                CTX.inputThread = std::thread(inputThread);')
    replace('                CTX.streaming = false;\n                CTX.inputThread.join();', '                stopInputThread();')
    # Joining/deleting stream textures in the STOP event follows any worker stop.
    replace('                GL(glDeleteTextures(2, CTX.streamTextures));', '                GL(glDeleteTextures(2, CTX.streamTextures));\n                CTX.streamTextures[0] = CTX.streamTextures[1] = 0;')
    # Do not destroy an old-context renderer after GL context recreation: its GL
    # names can collide with new resources. Normal pause has already released it.
    replace('    glInitialized = true;\n\n    CTX.glContextRecreated', '    glInitialized = true;\n    CTX.distortionRenderer = nullptr;\n\n    CTX.glContextRecreated')

    anchor = '        pauseNative();\n        glView.onPause();'
    if j.count(anchor) != 1:
        raise RuntimeError('Java lifecycle anchor mismatch')
    j = j.replace(anchor, '''        pauseNative();
        releaseGlBeforePause();
        glView.onPause();''', 1)
    anchor = '    private GLSurfaceView glView;'
    if j.count(anchor) != 1:
        raise RuntimeError('Java lifecycle field anchor mismatch')
    j = j.replace(anchor, anchor + '''
    // PhoneXR native lifecycle v1
    private native void releaseGlNative();
    private void releaseGlBeforePause() {
        final java.util.concurrent.CountDownLatch released = new java.util.concurrent.CountDownLatch(1);
        glView.queueEvent(() -> {
            try { releaseGlNative(); } finally { released.countDown(); }
        });
        try {
            if (!released.await(2, java.util.concurrent.TimeUnit.SECONDS))
                Log.w(TAG, "GL release delayed; continuing surface pause without UI-thread GL calls");
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
        }
    }
''', 1)
    cpp.write_text(c)
    java.write_text(j)
