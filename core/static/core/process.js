/* A local, responsive motion graphic. Playback never reads or changes portfolio data. */
(() => {
  "use strict";
  const player = document.querySelector("[data-process-player]");
  if (!player) return;
  const canvas = player.querySelector("[data-process-canvas]");
  const context = canvas.getContext("2d");
  if (!context) return;
  const stage = player.querySelector("[data-process-stage]");
  const playButton = player.querySelector("[data-process-play]");
  const playLabel = player.querySelector("[data-process-play-label]");
  const playIcon = player.querySelector("[data-process-play-icon]");
  const seek = player.querySelector("[data-process-seek]");
  const expandButton = player.querySelector("[data-process-expand]");
  const stepButtons = [...player.querySelectorAll("[data-process-step]")];
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const duration = 20;
  const steps = [
    { start: 0, settle: 1.5, label: "DOCUMENT", title: "Every insight starts with a document.", description: "Bring your contracts into one connected workspace." },
    { start: 3, settle: 6.2, label: "DETECT", title: "Find the fields that matter.", description: "EnginexAI identifies key information inside the document." },
    { start: 6.5, settle: 9.3, label: "EXTRACT", title: "Turn text into structured data.", description: "Extracted values stay connected to their original PDF page." },
    { start: 10, settle: 13.5, label: "PROCESS", title: "Keep the information connected.", description: "Link the evidence. Review the values. Explore the information." },
    { start: 14, settle: 18, label: "CHARTS", title: "See the story in your data.", description: "Turn your questions into comparisons, patterns and charts." },
  ];
  const C = { gold: "#e4c17a", goldDark: "#c99b3e", ink: "#142c42", white: "#f5f5ee", muted: "#a5b8c8", dim: "#7691a5", line: "#304b60", panel: "#122c42", teal: "#77c4b4", paper: "#f5f4ed" };
  const fields = [
    { label: "Tenant", value: "Resident 024" },
    { label: "Annual rent", value: "AED 120,000" },
    { label: "Lease end", value: "30 Sep 2027" },
    { label: "Property", value: "Al Rayyana" },
  ];
  let elapsed = 0;
  let playing = false;
  let lastFrame = null;
  let frameId = null;
  let visible = true;
  let width = 1200;
  let height = 530;
  let mobile = false;
  let stepIndex = -1;
  let expanded = false;
  let backgroundNodes = [];

  const clamp = x => Math.max(0, Math.min(1, x));
  const progress = (t, a, b) => clamp((t - a) / (b - a));
  const ease = x => 1 - (1 - clamp(x)) ** 3;
  const smooth = x => { x = clamp(x); return x * x * (3 - 2 * x); };
  const mix = (a, b, p) => a + (b - a) * p;
  const layer = (opacity, draw) => {
    if (opacity <= 0) return;
    context.save(); context.globalAlpha *= opacity; draw(); context.restore();
  };

  function rect(x, y, w, h, fill, radius = 0, stroke = null, lineWidth = 1) {
    context.beginPath();
    context.roundRect(x, y, Math.max(0, w), Math.max(0, h), radius);
    if (fill) { context.fillStyle = fill; context.fill(); }
    if (stroke) { context.strokeStyle = stroke; context.lineWidth = lineWidth; context.stroke(); }
  }
  function line(points, color = C.line, thickness = 1) {
    context.beginPath(); context.moveTo(...points[0]);
    points.slice(1).forEach(p => context.lineTo(...p));
    context.strokeStyle = color; context.lineWidth = thickness;
    context.lineCap = "round"; context.lineJoin = "round"; context.stroke();
  }
  function circle(x, y, r, fill, stroke = null, thickness = 1) {
    context.beginPath(); context.arc(x, y, r, 0, 2 * Math.PI);
    if (fill) { context.fillStyle = fill; context.fill(); }
    if (stroke) { context.strokeStyle = stroke; context.lineWidth = thickness; context.stroke(); }
  }
  function arc(x, y, r, end, color, thickness = 10) {
    if (end <= 0) return;
    context.beginPath(); context.arc(x, y, r, -Math.PI / 2, -Math.PI / 2 + end * Math.PI * 2);
    context.strokeStyle = color; context.lineWidth = thickness; context.lineCap = "round"; context.stroke();
  }
  function text(x, y, value, size = 20, color = C.white, weight = 400, align = "left") {
    context.font = `${weight} ${size}px Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`;
    context.fillStyle = color; context.textAlign = align; context.textBaseline = "top";
    context.fillText(String(value), x, y);
  }
  function check(x, y, s = 10, color = C.teal) {
    line([[x-s*.5,y],[x-s*.1,y+s*.35],[x+s*.65,y-s*.45]],color,2.5);
  }
  function sparkle(x, y, r = 20, color = C.gold) {
    context.beginPath();
    for (let i = 0; i < 8; i++) {
      const angle = i * Math.PI / 4 - Math.PI / 2;
      const radius = i % 2 ? r * .28 : r;
      const p = [x + Math.cos(angle) * radius, y + Math.sin(angle) * radius];
      if (i === 0) context.moveTo(...p); else context.lineTo(...p);
    }
    context.closePath(); context.fillStyle = color; context.fill();
  }

  function documentAt(x, y, scale = 1, detection = -1) {
    context.save(); context.translate(x, y); context.scale(scale, scale);
    rect(10,16,300,398,"#081725",13);
    rect(5,7,300,398,"#ced7d4",12);
    rect(0,0,300,398,C.paper,12);
    text(26,25,"E",28,C.ink,700);
    text(57,35,"ENGINEX / CONTRACTS",9,"#667c82",600);
    text(26,79,"LEASE AGREEMENT",20,C.ink,650);
    text(26,109,"Residential property · EX-024",11,"#657786");
    line([[26,137],[274,137]],"#d8dedb");
    fields.forEach((field, i) => {
      const fy = 154 + i * 48;
      text(26,fy,field.label.toUpperCase(),8,"#718188",600);
      text(26,fy+15,field.value,15,C.ink,500);
      line([[26,fy+39],[274,fy+39]],"#dfe2dc");
      const p = smooth(progress(detection, i*.5, i*.5+.35));
      layer(p, () => {
        rect(20,fy+11,261,25,null,3,C.goldDark,1.5);
        [[20,fy+11,1,1],[281,fy+11,-1,1],[20,fy+36,1,-1],[281,fy+36,-1,-1]].forEach(([a,b,u,v]) => line([[a,b+v*7],[a,b],[a+u*7,b]],C.goldDark,2));
      });
    });
    [242,200,224].forEach((w,i) => rect(26,357+i*9,w,2,"#ccd5d2",1));
    if (detection >= 0 && detection <= 2.15) {
      const sy = 145 + detection / 2.15 * 201;
      const glow = context.createLinearGradient(0,sy-12,0,sy+12);
      glow.addColorStop(0,"#c99b3e00"); glow.addColorStop(.5,"#c99b3e40"); glow.addColorStop(1,"#c99b3e00");
      rect(13,sy-12,274,24,glow);
      line([[12,sy],[289,sy]],C.goldDark,1.5);
      circle(289,sy,3,C.goldDark);
    }
    context.restore();
  }

  function drawDocument(t) {
    const enter = ease(progress(t,0,.9));
    const x = mobile ? 150 : 450;
    const y = mobile ? 106 : 38;
    documentAt(x,y+20*(1-enter));
    const cx = width/2;
    layer(enter, () => {
      rect(cx-97,y+433,194,34,"#233b4c",17,C.line);
      text(cx,y+443,"PDF · LEASE AGREEMENT",11,C.gold,600,"center");
    });
    if (!mobile) {
      layer(.8,() => {
        line([[160,240],[365,240]],C.line);
        line([[835,240],[1040,240]],C.line);
        circle(365,240,4,C.gold); sparkle(867,240,11);
        text(165,263,"SOURCE INFORMATION",10,C.dim,500);
        text(869,263,"CONNECTED INTELLIGENCE",10,C.dim,500);
      });
    }
  }

  function drawDetection(t) {
    const p = t - 3.25;
    const x = mobile ? 150 : 225;
    const y = mobile ? 28 : 42;
    documentAt(x,y,1,p);
    fields.forEach((field,i) => {
      const a=smooth(progress(p,i*.5,i*.5+.35));
      layer(a,() => {
        const cx=mobile ? 45+(i%2)*265 : 757;
        const cy=mobile ? 500+Math.floor(i/2)*77 : 101+i*83;
        if (!mobile) {
          const sy=y+177+i*48;
          line([[x+288,sy],[x+346,sy],[cx-27,cy+18],[cx,cy+18]],C.line);
          circle(x+288,sy,3,C.gold);
        }
        circle(cx+15,cy+18,15,"#254448",C.gold);
        check(cx+15,cy+18,10,C.gold);
        text(cx+44,cy+7,field.label,21,C.white,500);
        text(cx+44,cy+35,"FIELD DETECTED",10,C.dim,500);
      });
    });
  }

  function drawExtraction(t) {
    const shift = smooth(progress(t,6.5,7.2));
    const ds = mobile ? mix(1,.61,shift) : 1;
    const dx = mobile ? mix(150,208,shift) : mix(225,145,shift);
    const dy = mobile ? 28 : 42;
    documentAt(dx,dy,ds,3);
    fields.forEach((field,i) => {
      const a=smooth(progress(t,6.65+i*.23,7.3+i*.23));
      const x=mobile ? 35+(i%2)*280 : 657;
      const y=mobile ? 365+Math.floor(i/2)*108 : 71+i*87;
      const w=mobile ? 250 : 405;
      const h=mobile ? 87 : 70;
      const sx=dx+287*ds, sy=dy+(177+i*48)*ds;
      layer(a,() => {
        if (!mobile) line([[sx,sy],[sx+80,sy],[x-30,y+h/2],[x,y+h/2]],C.line);
        rect(x,y,w,h,C.panel,10,C.line);
        rect(x,y+15,3,h-30,C.gold,1);
        text(x+19,y+13,field.label.toUpperCase(),mobile ? 13 : 10,C.muted,550);
        text(x+19,y+(mobile ? 40 : 32),field.value,mobile ? 25 : 21,C.white,600);
        if (!mobile) { circle(x+w-27,y+35,11,"#234c4b"); check(x+w-27,y+35,8); }
      });
      const flight=progress(t,6.7+i*.32,7.55+i*.32);
      if (flight>0 && flight<1) {
        const p=ease(flight), ex=mobile ? x+w/2 : x, ey=y+h/2;
        const fx=mix(sx,ex,p),fy=mix(sy,ey,p)-35*Math.sin(p*Math.PI);
        rect(fx-18,fy-9,36,18,C.gold,5); line([[fx-8,fy],[fx+8,fy]],C.ink,2);
      }
    });
    layer(smooth(progress(t,8.25,8.8)),() => {
      const x=mobile ? 300 : 850;
      const y=mobile ? 626 : 449;
      text(x,y,"EX-024.pdf  ·  Page 1",mobile ? 20 : 16,C.gold,500,"center");
      text(x,y+30,"The source stays with every value.",mobile ? 17 : 12,C.muted,400,"center");
    });
  }

  function pipelineIcon(kind,x,y) {
    if (kind===0) {
      rect(x-14,y-20,28,38,null,3,C.gold,2);
      line([[x-7,y-8],[x+6,y-8]],C.gold,2);
      line([[x-7,y],[x+3,y]],C.gold,2);
      circle(x+13,y+12,9,C.panel,C.gold,2);
      line([[x+20,y+19],[x+27,y+26]],C.gold,2);
    } else if (kind===1) {
      circle(x,y,24,null,C.gold,2); check(x,y,24,C.gold);
    } else {
      sparkle(x,y,29); sparkle(x+28,y-24,8);
    }
  }

  function drawPipeline(t) {
    const xs=mobile ? [133,133,133] : [255,600,945];
    const ys=mobile ? [118,331,544] : [226,226,226];
    const labels=["Link sources","Review values","Analyze"];
    const subtitles=["Keep the original evidence","Confirm the information","Explore patterns and totals"];
    if (mobile) line([[133,25],[133,643]],C.line,2);
    else line([[78,226],[1122,226]],C.line,2);
    for (let j=0;j<7;j++) {
      const p=progress(t,10.35+j*.24,12.55+j*.24);
      if (p===0 || p===1) continue;
      const x=mobile ? 133 : mix(78,1122,p);
      const y=mobile ? mix(25,643,p) : 226;
      if (xs.some((cx,i)=>Math.hypot(x-cx,y-ys[i])<72)) continue;
      rect(x-16,y-10,32,20,j%2 ? C.teal : C.gold,5);
    }
    xs.forEach((x,i) => {
      const y=ys[i];
      const p=smooth(progress(t,10.4+i*.8,10.95+i*.8));
      circle(x,y,70,"#0e2439",p ? C.gold : C.line,1.5);
      circle(x,y,55,C.panel);
      pipelineIcon(i,x,y);
      layer(p,()=>arc(x,y,78,p,C.gold,1.5));
      const tx=mobile ? 252 : x;
      text(tx,mobile ? y-23 : y+105,labels[i],mobile ? 28 : 24,C.white,600,mobile ? "left" : "center");
      text(tx,mobile ? y+23 : y+143,subtitles[i],mobile ? 17 : 14,C.muted,400,mobile ? "left" : "center");
      if (!mobile) text(x,y-110,`0${i+1}`,12,C.gold,600,"center");
    });
    if (!mobile) layer(smooth(progress(t,12.6,13.1)),()=> {
      rect(431,445,338,35,"#19383f",18,"#345854");
      check(454,462,9); text(477,455,"Evidence stays with the information",12,C.teal,500);
    });
  }

  function chartCard(x,y,w,h,title,sub) {
    rect(x+1,y+7,w,h,"#081827",13);
    rect(x,y,w,h,C.panel,13,C.line);
    text(x+22,y+23,title,mobile ? 23 : 20,C.white,600);
    text(x+22,y+55,sub,mobile ? 16 : 11,C.muted);
  }
  function drawBarChart(t,x,y,w,h) {
    chartCard(x,y,w,h,"Annual rent","AED thousands");
    const left=x+45,right=x+w-22,bottom=y+h-52,top=y+111;
    const ch=bottom-top;
    [0,50,100,150].forEach(v=> {
      const gy=bottom-v/150*ch; line([[left,gy],[right,gy]],"#274257");
      text(left-10,gy-5,v,mobile ? 14 : 10,C.dim,400,"right");
    });
    const vals=[120,96,144,108,84,132];
    vals.forEach((v,i)=> {
      const p=ease(progress(t,14.4+i*.09,15.65+i*.09));
      const slot=(right-left)/6,bw=slot*.56;
      const bx=left+slot*i+slot*.22,bh=v/150*ch*p;
      if (bh>1) { rect(bx,bottom-bh,bw,bh,i===2 ? C.gold : "#609caa",4); rect(bx,bottom-4,bw,4,i===2 ? C.gold : "#609caa"); }
      text(bx+bw/2,bottom+15,String.fromCharCode(65+i),mobile ? 15 : 11,C.muted,500,"center");
      if (p>.98) text(bx+bw/2,bottom-bh-21,v,mobile ? 15 : 11,C.white,500,"center");
    });
  }
  function drawLineChart(t,x,y,w,h) {
    chartCard(x,y,w,h,"Lease expiries","Upcoming months");
    const left=x+38,right=x+w-24,bottom=y+h-55,top=y+116;
    [0,10,20,30].forEach(v=> {
      const gy=bottom-v/30*(bottom-top); line([[left,gy],[right,gy]],"#274257");
      text(left-10,gy-5,v,mobile ? 14 : 10,C.dim,400,"right");
    });
    const vals=[9,16,12,25,20,28];
    const pts=vals.map((v,i)=>[left+i*(right-left)/5,bottom-v/30*(bottom-top)]);
    const p=progress(t,14.65,16.45),path=[pts[0]];
    for (let i=0;i<5;i++) {
      const f=clamp(p*5-i);
      if (f>0) path.push([mix(pts[i][0],pts[i+1][0],f),mix(pts[i][1],pts[i+1][1],f)]);
    }
    if (path.length>1) {
      context.beginPath(); context.moveTo(left,bottom);
      path.forEach(pt=>context.lineTo(...pt)); context.lineTo(path.at(-1)[0],bottom);
      context.closePath(); context.fillStyle="#1b414e"; context.fill();
      line(path,C.teal,3); circle(...path.at(-1),4,C.white);
    }
    ["Oct","Nov","Dec","Jan","Feb","Mar"].forEach((label,i)=> {
      if (!mobile || i%2===0) text(pts[i][0],bottom+18,label,mobile ? 14 : 10,C.muted,400,"center");
    });
  }
  function drawDonut(t,x,y,w,h) {
    chartCard(x,y,w,h,"Occupancy","Unit status");
    const cx=x+w/2,cy=y+h*.53,r=Math.min(w*.29,h*.24);
    const p=ease(progress(t,14.8,16.8));
    arc(cx,cy,r,1,"#365165",mobile ? 18 : 20);
    arc(cx,cy,r,.88*p,C.gold,mobile ? 18 : 20);
    text(cx,cy-25,`${Math.round(88*p)}%`,mobile ? 39 : 42,C.white,600,"center");
    text(cx,cy+25,"Occupied",mobile ? 17 : 12,C.muted,400,"center");
    circle(x+25,y+h-54,4,C.gold); text(x+38,y+h-62,"Occupied 88%",mobile ? 16 : 12,C.muted);
    circle(x+25,y+h-28,4,"#607c92"); text(x+38,y+h-36,"Vacant 12%",mobile ? 16 : 12,C.muted);
  }
  function drawCharts(t) {
    if (mobile) {
      drawBarChart(t,30,15,540,300);
      drawLineChart(t,30,342,260,328);
      drawDonut(t,310,342,260,328);
    } else {
      drawBarChart(t,45,48,350,380);
      drawLineChart(t,425,48,350,380);
      drawDonut(t,805,48,350,380);
      layer(smooth(progress(t,17.1,17.8)),()=>text(600,470,"FROM DOCUMENTS TO DECISIONS",12,C.gold,550,"center"));
    }
  }

  function updateInterface() {
    let next=steps.findLastIndex(s=>elapsed>=s.start);
    if (next!==stepIndex) {
      stepIndex=next;
      const s=steps[next];
      player.querySelector("[data-process-counter]").textContent=`0${next+1} / 05 · ${s.label}`;
      player.querySelector("[data-process-title]").textContent=s.title;
      player.querySelector("[data-process-description]").textContent=s.description;
      stepButtons.forEach((button,i)=> {
        if (i===next) button.setAttribute("aria-current","step"); else button.removeAttribute("aria-current");
      });
    }
    seek.value=elapsed.toFixed(2);
    seek.style.setProperty("--progress",`${elapsed/duration*100}%`);
    seek.setAttribute("aria-valuetext",`${elapsed.toFixed(1)} of 20 seconds. ${steps[next].label.toLowerCase()}`);
    player.querySelector("[data-process-time]").textContent=`0:${String(Math.floor(elapsed)).padStart(2,"0")} / 0:20`;
    playLabel.textContent=playing ? "Pause" : elapsed>=duration ? "Replay" : "Play";
    playIcon.textContent=playing ? "Ⅱ" : elapsed>=duration ? "↺" : "▶";
    playButton.setAttribute("aria-label",playing ? "Pause animation" : elapsed>=duration ? "Replay animation" : "Play animation");
    player.dataset.playing=String(playing);
  }

  function draw() {
    context.clearRect(0,0,canvas.width,canvas.height);
    const scale=Math.min(canvas.width/width,canvas.height/height);
    context.save();
    context.translate((canvas.width-width*scale)/2,(canvas.height-height*scale)/2);
    context.scale(scale,scale);
    // Stable guide points supply visual continuity as the objects transform.
    for (let x=30;x<width;x+=35) for (let y=20;y<height;y+=35) circle(x,y,.7,"#28465a");
    const drawers=[drawDocument,drawDetection,drawExtraction,drawPipeline,drawCharts];
    const index=steps.findLastIndex(s=>elapsed>=s.start);
    const fade=index===0 ? 1 : smooth(progress(elapsed,steps[index].start,steps[index].start+.38));
    if (index>0 && fade<1) layer(1-fade,()=>drawers[index-1](steps[index].start));
    layer(fade,()=>drawers[index](elapsed));
    context.restore();
    updateInterface();
  }

  function resize() {
    const bounds=stage.getBoundingClientRect();
    if (!bounds.width || !bounds.height) return;
    mobile=bounds.width<=620;
    width=mobile ? 600 : 1200; height=mobile ? 700 : 530;
    const dpr=Math.min(window.devicePixelRatio || 1,2);
    canvas.width=Math.round(bounds.width*dpr); canvas.height=Math.round(bounds.height*dpr);
    draw();
  }
  function tick(now) {
    frameId=null;
    if (!playing || !visible || document.hidden) { lastFrame=null; return; }
    if (lastFrame!==null) elapsed=Math.min(duration,elapsed+(now-lastFrame)/1000);
    lastFrame=now;
    if (elapsed>=duration) { playing=false; lastFrame=null; }
    draw();
    schedule();
  }
  function schedule() {
    if (playing && visible && !document.hidden && frameId===null) frameId=requestAnimationFrame(tick);
  }
  function pause() {
    playing=false; lastFrame=null;
    if (frameId!==null) cancelAnimationFrame(frameId);
    frameId=null; updateInterface();
  }
  function play(restart=false) {
    if (restart || elapsed>=duration) elapsed=0;
    playing=true; lastFrame=null; draw(); schedule();
  }
  playButton.addEventListener("click",()=>playing ? pause() : play());
  player.querySelector("[data-process-replay]").addEventListener("click",()=>play(true));
  seek.addEventListener("input",()=> { elapsed=Number(seek.value); lastFrame=null; draw(); });
  stepButtons.forEach((button,i)=>button.addEventListener("click",()=> {
    pause(); elapsed=steps[i].settle; draw();
  }));

  function setExpanded(value) {
    expanded=value;
    player.classList.toggle("is-expanded",expanded);
    document.body.classList.toggle("process-expanded",expanded);
    expandButton.setAttribute("aria-pressed",String(expanded));
    player.querySelector("[data-expand-label]").textContent=expanded ? "Close" : "Expand";
    if (expanded) {
      // Keep the expanded player as the only keyboard and screen-reader surface.
      let node=player;
      while (node.parentElement) {
        for (const sibling of node.parentElement.children) {
          if (sibling!==node && !["SCRIPT","STYLE","META"].includes(sibling.tagName)) {
            backgroundNodes.push([sibling,sibling.inert]); sibling.inert=true;
          }
        }
        node=node.parentElement;
        if (node===document.body) break;
      }
      player.setAttribute("role","dialog"); player.setAttribute("aria-modal","true");
    } else {
      backgroundNodes.forEach(([node,wasInert])=>node.inert=wasInert); backgroundNodes=[];
      player.removeAttribute("role"); player.removeAttribute("aria-modal");
    }
    expandButton.focus({preventScroll:true}); resize();
  }
  expandButton.addEventListener("click",()=>setExpanded(!expanded));
  player.addEventListener("keydown",event=> {
    if (!expanded) return;
    if (event.key==="Escape") { event.preventDefault(); setExpanded(false); }
    if (event.key==="Tab") {
      const controls=[...player.querySelectorAll("button,input")];
      const first=controls[0],last=controls.at(-1);
      if (event.shiftKey && document.activeElement===first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement===last) { event.preventDefault(); first.focus(); }
    }
  });
  document.addEventListener("visibilitychange",()=> { lastFrame=null; schedule(); });
  reducedMotion.addEventListener("change",event=> { if (event.matches) pause(); });
  window.addEventListener("pagehide",()=> { pause(); if (expanded) setExpanded(false); });
  new ResizeObserver(resize).observe(stage);
  new IntersectionObserver(entries=> {
    visible=entries[0].isIntersecting; lastFrame=null; schedule();
  },{threshold:0}).observe(player);
  player.querySelector("[data-process-controls]").hidden=false;
  player.querySelector("[data-process-steps]").hidden=false;
  expandButton.hidden=false;
  resize();
  if (reducedMotion.matches) { elapsed=steps[0].settle; draw(); }
  else play();
})();
