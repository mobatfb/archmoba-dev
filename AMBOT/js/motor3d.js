/* AMBOT 0.1 - Motor 3D procedural WebGL con alternativa Canvas 2D.
   La geometría se construye en código, sin bibliotecas externas ni CDN. */
'use strict';
const AMBOT3D = (() => {
  const TAU = Math.PI*2, T = 1.35, RAD = Math.PI/180;
  const rgb = s => {const n=parseInt(s.slice(1),16);return [(n>>16&255)/255,(n>>8&255)/255,(n&255)/255];};
  const color = {
    ground:rgb('#06121f'),floor:rgb('#0b1f33'),floor2:rgb('#10253a'),
    wall:rgb('#17314e'),internal:rgb('#284766'),cyan:rgb('#5ceaff'),
    blue:rgb('#1abfe9'),pink:rgb('#ff77b4'),white:rgb('#e4faff'),
    dark:rgb('#10334f'),accent:rgb('#187795'),bright:rgb('#e0fbff')
  };
  const sub=(a,b)=>[a[0]-b[0],a[1]-b[1],a[2]-b[2]];
  const dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
  const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
  const norm=a=>{const l=Math.hypot(...a)||1;return a.map(x=>x/l);};
  const scale=(a,k)=>a.map(x=>x*k);
  const add=(a,b)=>a.map((x,i)=>x+b[i]);
  function matMul(a,b){const o=new Float32Array(16);for(let j=0;j<4;j++)for(let i=0;i<4;i++){let n=0;for(let k=0;k<4;k++)n+=a[k*4+i]*b[j*4+k];o[j*4+i]=n;}return o;}
  function perspective(fovy,aspect,near,far){const f=1/Math.tan(fovy/2),nf=1/(near-far);return new Float32Array([f/aspect,0,0,0,0,f,0,0,0,0,(far+near)*nf,-1,0,0,2*far*near*nf,0]);}
  function lookAt(eye,at){const z=norm(sub(eye,at)),x=norm(cross([0,1,0],z)),y=cross(z,x);
    return new Float32Array([x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-dot(x,eye),-dot(y,eye),-dot(z,eye),1]);}
  class Engine {
    constructor(canvas){
      this.canvas=canvas;this.gl=canvas.getContext('webgl',{antialias:true,alpha:false});
      if(!this.gl)this.ctx=canvas.getContext('2d');
      if(!this.gl&&!this.ctx)throw new Error('No se pudo crear el visor 3D.');
      this.map=[];this.robot={x:5,y:3,orientacion:'E',bateria:100,pasos:0};
      this.px=5;this.py=3;this.angle=Math.PI/2;
      this.yaw=.72;this.pitch=.86;this.distance=19;
      this.target=[0,.55,0];this.drag=false;this.lastPointer=[0,0];
      this.lastFrame=0;this.timer=0;this.vertices=[];
      if(this.gl)this.initGL();
      this.bind();
      requestAnimationFrame(t=>this.frame(t));
    }
    initGL(){
      const gl=this.gl;
      const vs='attribute vec3 aPos;attribute vec3 aCol;uniform mat4 uMVP;varying vec3 vCol;void main(){vCol=aCol;gl_Position=uMVP*vec4(aPos,1.0);}';
      const fs='precision mediump float;varying vec3 vCol;void main(){gl_FragColor=vec4(vCol,1.0);}';
      const compile=(kind,src)=>{const sh=gl.createShader(kind);gl.shaderSource(sh,src);gl.compileShader(sh);if(!gl.getShaderParameter(sh,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(sh));return sh;};
      const prog=gl.createProgram();gl.attachShader(prog,compile(gl.VERTEX_SHADER,vs));gl.attachShader(prog,compile(gl.FRAGMENT_SHADER,fs));gl.linkProgram(prog);
      if(!gl.getProgramParameter(prog,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(prog));
      this.program=prog;gl.useProgram(prog);this.buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,this.buffer);
      const pos=gl.getAttribLocation(prog,'aPos'),col=gl.getAttribLocation(prog,'aCol');
      gl.enableVertexAttribArray(pos);gl.enableVertexAttribArray(col);
      gl.vertexAttribPointer(pos,3,gl.FLOAT,false,24,0);gl.vertexAttribPointer(col,3,gl.FLOAT,false,24,12);
      this.mvpLoc=gl.getUniformLocation(prog,'uMVP');
      gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);gl.clearColor(.024,.058,.102,1);
    }
    bind(){
      const c=this.canvas;
      c.addEventListener('pointerdown',e=>{this.drag=true;this.lastPointer=[e.clientX,e.clientY];c.setPointerCapture(e.pointerId);});
      c.addEventListener('pointerup',()=>this.drag=false);
      c.addEventListener('pointercancel',()=>this.drag=false);
      c.addEventListener('pointermove',e=>{
        if(!this.drag)return;
        const dx=e.clientX-this.lastPointer[0],dy=e.clientY-this.lastPointer[1];
        this.yaw-=dx*.007;this.pitch=Math.max(.18,Math.min(1.45,this.pitch+dy*.006));
        this.lastPointer=[e.clientX,e.clientY];
      });
      c.addEventListener('wheel',e=>{e.preventDefault();this.distance=Math.max(7,Math.min(33,this.distance+e.deltaY*.013));},{passive:false});
      window.addEventListener('resize',()=>this.resize());this.resize();
    }
    resize(){
      const ratio=Math.min(window.devicePixelRatio||1,1.7),w=Math.max(2,Math.floor(this.canvas.clientWidth*ratio)),h=Math.max(2,Math.floor(this.canvas.clientHeight*ratio));
      if(this.canvas.width!==w||this.canvas.height!==h){this.canvas.width=w;this.canvas.height=h;if(this.gl)this.gl.viewport(0,0,w,h);}
    }
    resetCamera(){this.yaw=.72;this.pitch=.86;this.distance=19;}
    setMap(map){if(Array.isArray(map)&&map.length)this.map=map;}
    angleFor(o){return {N:0,E:Math.PI/2,S:Math.PI,O:-Math.PI/2}[o]||0;}
    setRobot(robot,snap){
      if(!robot)return;
      this.robot=Object.assign({},this.robot,robot);
      if(snap){this.px=robot.x;this.py=robot.y;this.angle=this.angleFor(robot.orientacion);}
    }
    world(x,y){return [(x-(this.map[0]?.length-1||10)/2)*T,(y-(this.map.length-1||7)/2)*T];}
    tri(a,b,c,col,shade=1){
      const cc=col.map(v=>Math.min(.99,v*shade));
      for(const p of [a,b,c])this.vertices.push(p[0],p[1],p[2],cc[0],cc[1],cc[2]);
    }
    quad(a,b,c,d,col,sh=1){this.tri(a,b,c,col,sh);this.tri(a,c,d,col,sh);}
    cube(x,y,z,sx,sy,sz,col){
      const a=sx/2,b=sy/2,c=sz/2;
      const p=[
        [x-a,y-b,z-c],[x+a,y-b,z-c],[x+a,y+b,z-c],[x-a,y+b,z-c],
        [x-a,y-b,z+c],[x+a,y-b,z+c],[x+a,y+b,z+c],[x-a,y+b,z+c]
      ];
      const faces=[
        [[4,5,6,7],.8],[[1,0,3,2],.62],[[5,1,2,6],.74],
        [[0,4,7,3],.62],[[7,6,2,3],1.04],[[0,1,5,4],.4]
      ];
      for(const [q,l] of faces)this.quad(p[q[0]],p[q[1]],p[q[2]],p[q[3]],col,l);
    }
    bone(a,b,r,col){
      const dir=norm(sub(b,a)),ref=Math.abs(dir[1])>.91?[0,0,1]:[0,1,0],u=scale(norm(cross(ref,dir)),r),v=scale(norm(cross(dir,u)),r);
      for(let i=0;i<8;i++){
        const phi=i*TAU/8,next=(i+1)*TAU/8;
        const ra=add(scale(u,Math.cos(phi)),scale(v,Math.sin(phi)));
        const rb=add(scale(u,Math.cos(next)),scale(v,Math.sin(next)));
        this.quad(add(a,ra),add(a,rb),add(b,rb),add(b,ra),col,.6+.4*Math.abs(Math.cos(phi)));
      }
    }
    sphere(center,r,col){
      const lat=8,lon=12;
      const p=(i,j)=>{const a=Math.PI*i/lat,b=TAU*j/lon;return [center[0]+r*Math.sin(a)*Math.cos(b),center[1]+r*Math.cos(a),center[2]+r*Math.sin(a)*Math.sin(b)];};
      for(let i=0;i<lat;i++)for(let j=0;j<lon;j++){
        const sh=.65+.35*Math.max(0,Math.cos(i*Math.PI/lat-.6));
        this.quad(p(i,j),p(i+1,j),p(i+1,j+1),p(i,j+1),col,sh);
      }
    }
    worldGeom(){
      const h=this.map.length,w=this.map[0]?.length||0;
      this.cube(0,-.19,0,w*T+.6,.28,h*T+.6,color.ground);
      for(let y=0;y<h;y++)for(let x=0;x<w;x++){
        const [px,pz]=this.world(x,y),border=x===0||y===0||x===w-1||y===h-1;
        if(this.map[y][x]==='#'){
          const height=border?.62:1.35;
          this.cube(px,height/2-.014,pz,T-.045,height,T-.045,border?color.wall:color.internal);
          this.cube(px,height+.006,pz,T-.13,.045,T-.13,color.accent);
          if(!border)this.cube(px,height+.055,pz,.18,.075,.18,color.pink);
        } else {
          this.cube(px,-.02,pz,T-.06,.038,T-.06,(x+y)%2?color.floor:color.floor2);
          if((x*y)%11===0)this.cube(px,.009,pz,.09,.015,.09,color.accent);
        }
      }
    }
    robotGeom(time,dt){
      const [bx,bz]=this.world(this.px,this.py),ang=this.angle,co=Math.cos(ang),si=Math.sin(ang);
      const moving=Math.abs(this.px-this.robot.x)+Math.abs(this.py-this.robot.y)>.04;
      this.timer+=dt*(moving?12:2.2);
      const swing=moving?Math.sin(this.timer)*.33:Math.sin(this.timer)*.027;
      const bob=moving?Math.abs(Math.sin(this.timer))*.06:Math.sin(time*.002)*.013;
      const p=(x,y,z)=>[bx+co*x-si*z,y+bob,bz+si*x+co*z];
      const limb=(a,b,r,c)=>this.bone(p(...a),p(...b),r,c);
      const joint=(a,r,c)=>this.sphere(p(...a),r,c);
      const hips=[[-.16,1.0,0],[.16,1.0,0]],knees=[[-.20,.56,-swing*.35],[.20,.56,swing*.35]],feet=[[-.23,.12,-swing*.55],[.23,.12,swing*.55]];
      for(let i=0;i<2;i++){
        limb(hips[i],knees[i],.080,color.white);
        limb(knees[i],feet[i],.075,color.cyan);
        joint(knees[i],.091,color.blue);joint(feet[i],.105,color.white);
      }
      limb([0,1.03,0],[0,1.79,0],.13,color.white);
      limb([-.29,1.79,0],[.29,1.79,0],.082,color.cyan);
      const shoulders=[[-.29,1.78,0],[.29,1.78,0]],elbows=[[-.49,1.36,swing*.56],[.49,1.36,-swing*.56]],hands=[[-.54,1.01,swing*.8],[.54,1.01,-swing*.8]];
      for(let i=0;i<2;i++){limb(shoulders[i],elbows[i],.078,color.cyan);limb(elbows[i],hands[i],.068,color.white);joint(hands[i],.092,color.white);}
      joint([0,1.48,-.13],.13,color.pink);
      joint([0,2.30,0],.30,color.bright);
      joint([-.11,2.32,-.275],.045,color.dark);
      joint([.11,2.32,-.275],.045,color.dark);
      limb([0,2.58,0],[0,2.79,0],.025,color.cyan);
      joint([0,2.81,0],.065,color.pink);
      for(let i=0;i<28;i++){
        const a=i*TAU/28,b=(i+1)*TAU/28;
        this.bone([bx+Math.cos(a)*.52,.065,bz+Math.sin(a)*.52],[bx+Math.cos(b)*.52,.065,bz+Math.sin(b)*.52],.025,color.blue);
      }
    }
    frame(time){
      requestAnimationFrame(t=>this.frame(t));
      if(!this.map.length)return;
      this.resize();const dt=Math.min(.055,(time-this.lastFrame)/1000||.016);this.lastFrame=time;
      const f=Math.min(1,dt*8.8);
      this.px+=(this.robot.x-this.px)*f;this.py+=(this.robot.y-this.py)*f;
      let delta=this.angleFor(this.robot.orientacion)-this.angle;
      while(delta>Math.PI)delta-=TAU;while(delta<-Math.PI)delta+=TAU;
      this.angle+=delta*f;
      this.vertices=[];this.worldGeom();this.robotGeom(time,dt);
      const eye=[this.target[0]+Math.sin(this.yaw)*Math.cos(this.pitch)*this.distance,
        this.target[1]+Math.sin(this.pitch)*this.distance,
        this.target[2]+Math.cos(this.yaw)*Math.cos(this.pitch)*this.distance];
      const aspect=this.canvas.width/this.canvas.height;
      if(this.gl){
        const gl=this.gl;
        gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
        gl.useProgram(this.program);gl.bindBuffer(gl.ARRAY_BUFFER,this.buffer);
        gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(this.vertices),gl.DYNAMIC_DRAW);
        gl.uniformMatrix4fv(this.mvpLoc,false,matMul(perspective(50*RAD,aspect,.1,85),lookAt(eye,this.target)));
        gl.drawArrays(gl.TRIANGLES,0,this.vertices.length/6);
      } else {
        const ctx=this.ctx,w=this.canvas.width,h=this.canvas.height;
        const bg=ctx.createLinearGradient(0,0,0,h);
        bg.addColorStop(0,'#07182d');bg.addColorStop(1,'#03111e');ctx.fillStyle=bg;ctx.fillRect(0,0,w,h);
        const forward=norm(sub(this.target,eye)),right=norm(cross(forward,[0,1,0])),up=cross(right,forward),focus=h/(2*Math.tan(25*RAD));
        const project=p=>{const d=sub(p,eye),z=dot(d,forward);if(z<.1)return null;return [w/2+dot(d,right)*focus/z,h/2-dot(d,up)*focus/z,z];};
        const tris=[];
        for(let i=0;i<this.vertices.length;i+=18){
          const p=[],v=this.vertices;
          for(let j=0;j<3;j++)p.push(project([v[i+j*6],v[i+j*6+1],v[i+j*6+2]]));
          if(p.some(x=>!x))continue;
          const c=[v[i+3],v[i+4],v[i+5]].map(x=>Math.round(x*255));
          tris.push({p,depth:(p[0][2]+p[1][2]+p[2][2])/3,col:'rgb('+c.join(',')+')'});
        }
        tris.sort((a,b)=>b.depth-a.depth);
        for(const t of tris){ctx.beginPath();ctx.moveTo(t.p[0][0],t.p[0][1]);ctx.lineTo(t.p[1][0],t.p[1][1]);ctx.lineTo(t.p[2][0],t.p[2][1]);ctx.closePath();ctx.fillStyle=t.col;ctx.fill();}
      }
    }
  }
  return {Engine};
})();
