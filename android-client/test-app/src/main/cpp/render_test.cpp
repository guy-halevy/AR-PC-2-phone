#include <jni.h>
#include <EGL/egl.h>
#include <GLES3/gl3.h>
#include <vector>
#include <stdexcept>
#include <string>
struct AlvrQuat { float x,y,z,w; };
struct AlvrPose { AlvrQuat orientation; float position[3]; };
struct AlvrFov { float left,right,up,down; };
#include "phonexr_hands.hpp"
static void require(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
extern "C" JNIEXPORT jstring JNICALL
Java_viritualisres_phonevr_xr_XrInstrumentationTest_renderProbe(JNIEnv* env,jclass){
    EGLDisplay display=eglGetDisplay(EGL_DEFAULT_DISPLAY);
    EGLContext context=EGL_NO_CONTEXT;EGLSurface surface=EGL_NO_SURFACE;
    std::string result;
    try {
        require(eglInitialize(display,nullptr,nullptr),"EGL initialize");
        const EGLint attrs[]={EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_RENDERABLE_TYPE,0x40,
            EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_ALPHA_SIZE,8,EGL_NONE};
        EGLConfig config;EGLint count=0;
        require(eglChooseConfig(display,attrs,&config,1,&count)&&count==1,"GLES3 config");
        const EGLint ctxAttrs[]={EGL_CONTEXT_CLIENT_VERSION,3,EGL_NONE};
        const EGLint surfAttrs[]={EGL_WIDTH,96,EGL_HEIGHT,96,EGL_NONE};
        context=eglCreateContext(display,config,EGL_NO_CONTEXT,ctxAttrs);
        surface=eglCreatePbufferSurface(display,config,surfAttrs);
        require(eglMakeCurrent(display,surface,surface,context),"EGL current");
        phonexr::handRenderer.reset();
        GLuint textures[3],fbo;glGenTextures(3,textures);glGenFramebuffers(1,&fbo);
        for(GLuint texture:textures){
            glBindTexture(GL_TEXTURE_2D,texture);glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA8,96,96,0,GL_RGBA,GL_UNSIGNED_BYTE,nullptr);
            glBindFramebuffer(GL_FRAMEBUFFER,fbo);glFramebufferTexture2D(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,texture,0);
            require(glCheckFramebufferStatus(GL_FRAMEBUFFER)==GL_FRAMEBUFFER_COMPLETE,"Texture framebuffer");
            glClearColor(0,0,0,1);glClear(GL_COLOR_BUFFER_BIT);
        }
        {std::lock_guard<std::mutex> lock(phonexr::handSnapshot.mutex);
            phonexr::handSnapshot.count=1;phonexr::handSnapshot.capture=1000000000;
            for(int i=0;i<21;i++){phonexr::handSnapshot.points[i*3]=(i%5-2)*.015f;phonexr::handSnapshot.points[i*3+1]=(i/5-2)*.02f;phonexr::handSnapshot.points[i*3+2]=-1;}}
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER,0);glViewport(7,8,21,22);
        glEnable(GL_SCISSOR_TEST);glScissor(0,0,1,1);glEnable(GL_DEPTH_TEST);glColorMask(false,true,false,true);
        const AlvrFov fov={-.7f,.7f,.7f,-.7f};
        double centroid[2]={};
        for(int eye=0;eye<3;eye++){
            AlvrPose pose={{0,0,0,1},{eye==0?-.032f:.032f,0,0}};
            phonexr::renderHands(textures[eye],96,96,pose,fov,eye==2?1150000001:1000000100);
            GLint viewport[4],bound;GLboolean mask[4];glGetIntegerv(GL_VIEWPORT,viewport);glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING,&bound);glGetBooleanv(GL_COLOR_WRITEMASK,mask);
            require(viewport[0]==7&&viewport[1]==8&&viewport[2]==21&&viewport[3]==22&&bound==0,"Renderer changed viewport/framebuffer");
            require(glIsEnabled(GL_SCISSOR_TEST)&&glIsEnabled(GL_DEPTH_TEST)&&!mask[0]&&mask[1]&&!mask[2]&&mask[3],"Renderer changed GL flags");
            glBindFramebuffer(GL_READ_FRAMEBUFFER,fbo);glFramebufferTexture2D(GL_READ_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,textures[eye],0);
            std::vector<unsigned char> pixels(96*96*4);glReadPixels(0,0,96,96,GL_RGBA,GL_UNSIGNED_BYTE,pixels.data());
            int lit=0;double sum=0;for(int i=0;i<96*96;i++)if(pixels[4*i+1]>100){++lit;sum+=i%96;}
            if(eye==2)require(lit==0,"Stale hands were rendered");
            else {require(lit>15,"No hand pixels rendered");centroid[eye]=sum/lit;}
        }
        require(centroid[0]>centroid[1]+1,"Wrong stereo disparity");
        require(glGetError()==GL_NO_ERROR,"GL error");
        glDeleteTextures(3,textures);glDeleteFramebuffers(1,&fbo);
    }catch(const std::exception& error){result=error.what();}
    if(display!=EGL_NO_DISPLAY){eglMakeCurrent(display,EGL_NO_SURFACE,EGL_NO_SURFACE,EGL_NO_CONTEXT);if(surface!=EGL_NO_SURFACE)eglDestroySurface(display,surface);if(context!=EGL_NO_CONTEXT)eglDestroyContext(display,context);eglTerminate(display);}
    phonexr::handRenderer.reset();
    return env->NewStringUTF(result.c_str());
}
