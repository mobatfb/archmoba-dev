<?php
declare(strict_types=1);
header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: private, no-store');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
// Nonce allows a built-in stylesheet without weakening the CSP for scripts.
$styleNonce = base64_encode(random_bytes(16));
header("Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self' 'nonce-{$styleNonce}'; img-src 'self' data: blob:; connect-src 'self' wss:; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'");
// Prefer the local stylesheet when installed; fallback works if it was omitted.
$embeddedStyle = <<<'MULTIMANDO_CSS_FALLBACK'
:root{color-scheme:dark;--bg:#060d1c;--ink:#f0f7ff;--muted:#88a4c2;--cyan:#5be1fb;--lime:#a8f69a;--gold:#ffd687;--pink:#ff759d;--stroke:#294363;--outline:#71e7f6;--key-size:clamp(55px,min(21.5vw,18dvh),133px);--stick-size:min(45vw,49dvh,400px)}
*{box-sizing:border-box}
html{font-family:Inter,ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif;background:var(--bg);color:var(--ink);font-size:14px}
body{margin:0;min-width:280px;background:radial-gradient(ellipse 72vw 55vh at 90% -15%,#23466d85,transparent 77%),radial-gradient(ellipse 65vw 55vh at -20% 90%,#3d225665,transparent 75%),var(--bg)}
button,input{font:inherit}button{cursor:pointer}button:disabled{cursor:not-allowed;opacity:.43}button:focus-visible,input:focus-visible,summary:focus-visible,.joystick-frame:focus-visible{outline:2px solid var(--outline);outline-offset:3px}
.app-shell{width:min(1180px,calc(100% - 24px));height:100vh;height:100dvh;min-height:340px;margin:auto;padding:clamp(7px,1.2dvh,16px) 0;display:grid;grid-template-rows:auto auto auto minmax(0,1fr) auto;gap:clamp(5px,1.2dvh,12px)}
.app-header{display:flex;justify-content:space-between;align-items:center;gap:12px;min-height:44px}
.brand{display:flex;align-items:center;gap:11px;min-width:0}.brand-mark{position:relative;flex:none;display:grid;place-items:center;width:41px;height:41px;font-size:26px;font-weight:950;font-style:italic;border-radius:12px;background:linear-gradient(140deg,#19366a,#18234b);border:1px solid #537aaa;box-shadow:0 0 23px #397dfa25}.brand-spark{position:absolute;right:-3px;top:-3px;width:8px;height:8px;background:var(--cyan);border-radius:50%;box-shadow:0 0 13px var(--cyan)}.brand strong{display:block;font-weight:950;letter-spacing:.11em;font-size:19px;line-height:1.12;white-space:nowrap}.brand small{display:block;font-size:9px;color:var(--muted);letter-spacing:.16em;font-weight:750;margin-top:4px}
.connection-pill{display:inline-flex;align-items:center;gap:8px;background:#11233b;border:1px solid #314b68;border-radius:30px;padding:9px 13px;color:#9bb6ce;font-size:10px;font-weight:850;letter-spacing:.075em;white-space:nowrap}.pulse{width:8px;height:8px;border-radius:50%;background:#657e9c;box-shadow:0 0 0 3px #52647c28}.connection-pill.online{color:var(--lime);border-color:#5e835d}.connection-pill.online .pulse{background:var(--lime);box-shadow:0 0 12px var(--lime)}.connection-pill.pending{color:var(--gold)}.connection-pill.pending .pulse{background:var(--gold)}
.connect-panel{position:relative;z-index:5;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center;background:linear-gradient(110deg,#132c49,#0c1c34);padding:9px 12px;border-radius:15px;border:1px solid var(--stroke)}
.nickname-field{display:flex;align-items:center;gap:12px;min-width:0}.nickname-field span{flex:none;font-size:10px;letter-spacing:.11em;font-weight:900;color:#afc5dc}.nickname-field input{min-width:0;max-width:480px;width:100%;height:38px;border-radius:9px;border:1px solid #365273;background:#08162c;color:#fff;padding:0 12px;outline:none;font-size:13px}.nickname-field input::placeholder{color:#6886a5}
.connect-tools{display:flex;gap:7px;align-items:center}.connect-btn,.disconnect-btn{height:38px;padding:0 clamp(10px,1.5vw,18px);border-radius:9px;border:1px solid #37516b;font-size:11px;letter-spacing:.04em;font-weight:950}.connect-btn{color:#05233a;background:linear-gradient(115deg,#7cfdff,#64baff);border:0;box-shadow:0 4px 14px #40d6ff18}.disconnect-btn{color:#e7f4fd;background:#142842}
.manual-connection{position:relative}.manual-connection summary{list-style:none;display:flex;align-items:center;justify-content:center;gap:6px;min-width:43px;height:38px;cursor:pointer;border:1px solid #38516b;border-radius:9px;background:#152841;color:#a8d8ed;font-size:12px;font-weight:800;user-select:none}.manual-connection summary::-webkit-details-marker{display:none}.manual-connection[open] summary{border-color:var(--cyan)}.manual-popover{position:absolute;right:0;top:calc(100% + 10px);width:min(340px,calc(100vw - 28px));background:#102640;border:1px solid #3e607f;border-radius:12px;padding:14px;box-shadow:0 18px 35px #000a}.manual-popover label{display:block;margin-bottom:9px;font-size:10px;font-weight:850;color:var(--cyan)}.manual-popover input{width:100%;min-width:0;padding:10px;border:1px solid #3c5873;border-radius:8px;background:#07172b;color:white;outline:none;font-size:12px}.manual-popover small{display:block;margin-top:8px;color:#a6bbd0;font-size:10px;line-height:1.4}
.error-text{position:absolute;z-index:9;left:12px;right:12px;top:calc(100% + 4px);border-radius:8px;border:1px solid #91485d;background:#442137;padding:10px;color:#ffb3c1;font-size:12px;box-shadow:0 10px 20px #0007}.error-text[hidden]{display:none}
.status-hud{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.stat{min-width:0;position:relative;display:grid;grid-template-columns:1fr auto;grid-template-rows:auto auto;align-items:center;column-gap:12px;padding:9px clamp(9px,1.5vw,17px);border:1px solid #2c4767;border-radius:13px;background:linear-gradient(145deg,#112742,#0b1c35)}.stat:before{content:"";position:absolute;left:11px;top:0;width:44px;height:2px;background:var(--cyan)}.stat:nth-child(2):before{background:#b797ff}.stat:nth-child(3):before{background:#ffa1c2}.stat>span{font-size:9px;letter-spacing:.12em;font-weight:850;color:#9cb6d2}.stat strong{grid-column:2;grid-row:1/span 2;color:#fff;font-size:clamp(20px,3vw,30px);font-weight:950;letter-spacing:-.03em;font-variant-numeric:tabular-nums}.stat small{grid-row:2;grid-column:1;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%;font-size:10px;color:#8ba7c4}.stat strong.urgent{color:var(--pink)}
.control-deck{min-height:0;display:grid;grid-template-rows:auto minmax(0,1fr) auto;border:1px solid #2b486a;border-radius:20px;overflow:hidden;background:radial-gradient(ellipse 45% 120% at 0% 90%,#3927516e,transparent),linear-gradient(145deg,#102845,#071728 75%);box-shadow:0 18px 42px #0005}
.deck-header{padding:clamp(9px,1.35dvh,15px) clamp(11px,1.8vw,22px);display:flex;align-items:center;justify-content:space-between;gap:10px;border-bottom:1px solid #203c58}.deck-title{display:flex;align-items:center;gap:10px;min-width:0}.deck-title strong{font-size:12px;letter-spacing:.14em;font-weight:950;white-space:nowrap}.deck-title small{font-size:10px;color:#8faac4;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.tiny-led{width:8px;height:8px;flex:none;border-radius:100%;background:var(--cyan);box-shadow:0 0 13px #5be1fb96}.deck-badges{display:flex;gap:8px;justify-content:flex-end;align-items:center}.deck-badges>span{border:1px solid #354d65;border-radius:8px;padding:6px 8px;font-size:9px;font-weight:850;white-space:nowrap;color:#98b6d3}.deck-badges .slot-indicator{border-color:#65578c;color:#cdbdff}.deck-badges .slot-indicator.active{border-color:#56c6d0;background:#52bad21a;color:var(--cyan)}
.controls{min-height:0;display:grid;grid-template-columns:1fr 1fr;gap:clamp(8px,2.5vw,30px);align-items:center;justify-items:center;padding:8px clamp(4px,2vw,18px)}.joystick-zone,.action-zone{min-width:0;min-height:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:clamp(7px,1.3dvh,14px);width:100%}.control-label{font-size:10px;letter-spacing:.16em;font-weight:900;color:#b3cbe4;white-space:nowrap}.joystick-frame{width:var(--stick-size);height:var(--stick-size);flex:none;position:relative;isolation:isolate;border:2px solid #3b5e81;border-radius:50%;background:radial-gradient(circle at 50% 48%,#273f61 0,#142945 33%,#08192e 59%,#142943 60%,#0b1c33 75%);box-shadow:inset 0 0 29px #0009,0 11px 26px #0006,0 0 0 6px #24426422;touch-action:none;user-select:none;cursor:grab}.joystick-frame.engaged{border-color:var(--cyan);box-shadow:inset 0 0 32px #0009,0 0 20px #53e3fb40}.joystick-base{position:absolute;inset:22%;display:grid;place-items:center;pointer-events:none}.joystick-thumb{position:relative;display:grid;place-items:center;width:60%;height:60%;min-width:58px;min-height:58px;max-width:124px;max-height:124px;border-radius:50%;background:radial-gradient(circle at 30% 23%,#708aa7,#2a4565 39%,#0f223d 75%);border:3px solid #6482a4;box-shadow:inset 0 0 0 5px #10233b,0 6px 15px #000a,0 0 0 2px #101b30;transition:transform .07s linear;will-change:transform}.joystick-frame.engaged .joystick-thumb{transition:none}.thumb-light{width:23%;height:23%;border:3px solid #a2bdd28c;border-radius:50%;background:#163551;box-shadow:0 0 9px #64b8ed66}.joystick-grid:before,.joystick-grid:after{content:"";position:absolute;background:#8eafc022;inset:auto}.joystick-grid:before{height:1px;width:65%;left:17%;top:50%}.joystick-grid:after{width:1px;height:65%;top:17%;left:50%}.joystick-label{position:absolute;font-size:clamp(9px,1.3vw,15px);font-weight:900;color:#73cde49b;pointer-events:none}.north{top:5%;left:48%}.south{bottom:5%;left:48%}.west{left:6%;top:48%}.east{right:6%;top:48%}
/* Seis botones: primera fila A B C; segunda fila D E F. */
.action-buttons{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));grid-template-rows:repeat(2,auto);gap:clamp(6px,1.5dvh,14px) clamp(5px,1.3vw,14px);width:min(100%,clamp(208px,34vw,414px));justify-content:center}
.action-btn{aspect-ratio:1;min-width:0;width:100%;display:grid;place-items:center;border:clamp(3px,.48vw,5px) solid #2c496a;color:#fff;border-radius:50%;font-weight:950;font-size:clamp(20px,3.2vw,39px);touch-action:none;user-select:none;box-shadow:inset 0 6px 12px #fff2,inset 0 -12px 18px #0005,0 6px 0 #050d1d,0 9px 15px #0008;transition:transform .07s,filter .07s,box-shadow .07s}
/* Nuevo orden: X Y L / A B R. Los codigos logicos no se modifican. */
.btn-x{background:linear-gradient(145deg,#62b4ff,#235ca9)}.btn-y{background:linear-gradient(145deg,#ffdf74,#ac7a1d)}.btn-l{background:linear-gradient(145deg,#a0afbf,#475568)}
.btn-a{background:linear-gradient(145deg,#7ae9ad,#26875c)}.btn-b{background:linear-gradient(145deg,#ff8390,#a62d41)}.btn-r{background:linear-gradient(145deg,#a0afbf,#475568)}
.action-btn.pressed,.action-btn:active{transform:translateY(4px);filter:brightness(1.22);box-shadow:inset 0 5px 13px #0004,0 2px 0 #050d1d}
.aux-buttons{display:flex;justify-content:center;gap:clamp(6px,1vw,15px);width:100%}.aux-btn{min-width:0;width:clamp(76px,10vw,118px);height:clamp(30px,5dvh,38px);border:1px solid #436887;border-radius:22px;background:#173655;color:#dae9fb;font-size:10px;font-weight:900;letter-spacing:.05em;touch-action:none;user-select:none}.aux-btn.aux-primary{color:#062339;background:var(--cyan);border-color:#91eefa}.aux-btn.pressed,.aux-btn:active{filter:brightness(1.18);transform:scale(.97)}.micro-hint{font-size:9px;letter-spacing:.08em;font-weight:750;color:#789ebc;white-space:nowrap}
.deck-footer{display:flex;align-items:center;gap:8px;padding:clamp(8px,1.3dvh,13px) clamp(11px,1.8vw,22px);border-top:1px solid #213a58;min-width:0}.feedback-indicator{width:7px;height:7px;border-radius:50%;flex:none;background:#7594b2}.deck-footer p{margin:0;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:11px;color:#a9c5df}.deck-footer>span:last-child{font-size:9px;font-weight:850;color:#7799b6;white-space:nowrap}.deck-footer p.feedback-error{color:#ff9ab4}.deck-footer p.feedback-success{color:#a2f2b9}.deck-footer p.feedback-warn{color:#ffdc90}
footer{text-align:center;color:#6487a5;letter-spacing:.06em;font-size:9px;font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding:0 4px;line-height:1.2}
@media(max-width:680px){:root{--key-size:clamp(50px,min(21vw,13dvh),105px);--stick-size:min(45vw,41dvh,290px)}.app-shell{width:calc(100% - 16px);gap:6px;padding:8px 0}.app-header{min-height:40px}.brand-mark{width:34px;height:34px;border-radius:9px;font-size:22px}.brand{gap:8px}.brand strong{font-size:15px}.brand small{font-size:8px;letter-spacing:.08em}.connection-pill{font-size:8px;padding:8px 9px;gap:6px}.pulse{width:7px;height:7px}.connect-panel{gap:6px;padding:7px}.nickname-field{gap:8px}.nickname-field span{display:none}.nickname-field input{height:36px;font-size:12px;padding:0 9px}.manual-label{display:none}.manual-connection summary{height:36px;min-width:35px}.connect-btn,.disconnect-btn{height:36px;padding:0 9px;font-size:10px}.status-hud{gap:5px}.stat{padding:8px;display:block;min-width:0}.stat:before{left:9px;width:27px}.stat span{display:block;font-size:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.stat strong{display:block;margin:2px 0;font-size:clamp(19px,5vw,27px)}.stat small{font-size:9px}.control-deck{border-radius:14px}.deck-header{padding:9px}.deck-title{gap:6px}.deck-title strong{font-size:10px;letter-spacing:.075em}.deck-title small{display:none}.deck-badges{gap:5px}.deck-badges>span{font-size:8px;padding:5px}.deck-badges>span:first-child{display:none}.controls{gap:5px;padding:7px 3px}.joystick-zone,.action-zone{gap:9px}.control-label{font-size:8px}.action-buttons{width:min(100%,clamp(130px,42vw,260px));gap:6px}.action-btn{font-size:clamp(18px,5vw,27px);border-width:3px}.joystick-thumb{min-width:52px;min-height:52px;border-width:3px}.micro-hint{font-size:7px;letter-spacing:0}.aux-btn{width:clamp(64px,18vw,93px);height:32px;font-size:9px}.deck-footer{padding:9px}.deck-footer p{font-size:10px}.deck-footer>span:last-child{display:none}footer{font-size:8px}}
@media(max-height:560px){:root{--key-size:clamp(43px,min(18vw,17dvh),115px);--stick-size:min(39vw,44dvh,330px)}.app-shell{gap:5px;padding:5px 0}.app-header{min-height:32px}.brand-mark{width:30px;height:30px;font-size:19px}.brand strong{font-size:15px}.brand small{font-size:7px;margin-top:1px}.connection-pill{padding:5px 9px}.connect-panel{padding:5px 8px}.nickname-field input,.connect-btn,.disconnect-btn,.manual-connection summary{height:31px}.status-hud .stat{padding:5px 10px}.stat strong{font-size:20px}.stat small{font-size:9px}.deck-header{padding:5px 10px}.deck-footer{padding:5px 10px}.controls{padding:4px}.joystick-zone,.action-zone{gap:4px}.control-label,.micro-hint{font-size:8px}.aux-btn{height:28px}.action-buttons{gap:5px}}
@media(max-width:340px){.connect-btn,.disconnect-btn{padding:0 6px;font-size:9px}.brand strong{font-size:13px}.connection-pill{font-size:7px}.stat small{font-size:8px}.micro-hint{display:none}.deck-footer p{font-size:9px}}
@media(prefers-reduced-motion:reduce){*,*:before,*:after{transition:none!important;animation:none!important}}
@media(max-width:600px) and (min-height:720px){:root{--stick-size:min(57vw,26dvh,244px);--key-size:clamp(65px,min(22vw,10dvh),94px)}.controls{grid-template-columns:1fr;grid-template-rows:auto auto;align-content:start;gap:2px;padding:4px 4px 8px}.joystick-zone{gap:4px;margin-top:-14px}.action-zone{gap:5px;margin-top:18px}.action-buttons{width:min(100%,clamp(210px,74vw,300px));gap:8px}.aux-buttons{gap:12px}.micro-hint{font-size:8px}}

/* Preferencia de teclas: configuración local del jugador, sin administración. */
.keys-config-btn{display:inline-flex;align-items:center;justify-content:center;height:28px;min-width:55px;padding:0 8px;border:1px solid #5bc6dc;border-radius:8px;background:#143650;color:#80e4f9;font-size:9px;font-weight:900;letter-spacing:.045em;white-space:nowrap}
.keys-config-btn:hover{background:#215172}.keys-config-btn:active{transform:translateY(1px)}
.key-dialog{position:fixed;inset:0;margin:auto;width:min(620px,calc(100vw - 22px));max-width:620px;max-height:calc(100dvh - 24px);padding:14px;border:1px solid #4c7899;border-radius:17px;color:#f4f8ff;background:#0d2138;box-shadow:0 24px 70px #000e;overflow:auto;z-index:80}
.key-dialog::backdrop{background:#020716d9;backdrop-filter:blur(5px)}
.key-dialog-head{display:flex;align-items:center;justify-content:space-between;gap:8px}.key-dialog-head strong{display:block;font-size:17px;letter-spacing:.07em}.key-dialog-head small{display:block;margin-top:4px;font-size:10px;color:#91b4d0;line-height:1.4}
.key-dialog-close{flex:none;border:1px solid #3c5675;border-radius:7px;background:#203850;color:#d9e9ff;font-size:10px;font-weight:850;padding:9px}
.key-instructions{margin:9px 0;color:#b5cbe1;font-size:12px;line-height:1.4}
.key-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.key-bind{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:8px 9px;background:#152e49;border:1px solid #36536f;border-radius:9px;min-width:0}.key-bind-name{font-size:12px;font-weight:900;white-space:nowrap}.key-bind small{display:block;font-size:9px;font-weight:700;color:#89aec8}.key-bind button{min-width:86px;max-width:58%;height:34px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding:0 9px;border:1px solid #6386a2;border-radius:7px;background:#0b1d34;color:#ddf3ff;font-size:11px;font-weight:850}.key-bind button.listening{background:#215877;color:#fff;outline:2px solid #65ecff;border-color:#65ecff}
.key-message{min-height:17px;margin:10px 0;color:#a2dfe9;font-size:11px}.key-dialog-foot{display:flex;justify-content:flex-end;gap:8px}.key-dialog-foot button{border:1px solid #426582;border-radius:9px;padding:10px 12px;background:#173d5a;color:#e4f6ff;font-size:11px;font-weight:850}.key-dialog-foot #saveKeys{background:#70dbef;color:#072037;border-color:#70dbef}
@media(max-width:680px){.keys-config-btn{min-width:50px;padding:0 6px;font-size:8px;height:26px}}
@media(max-width:350px){.deck-badges .slot-indicator{font-size:7px;padding:5px 3px}.keys-config-btn{font-size:8px;padding:0 4px;min-width:44px}}
@media(max-width:480px){.key-dialog{padding:12px;max-height:calc(100dvh - 12px)}.key-dialog-head strong{font-size:14px}.key-bind{padding:6px;gap:4px}.key-bind button{min-width:57px;font-size:10px;padding:0 5px;height:32px}.key-bind-name{font-size:10px}.key-bind small{font-size:8px}.key-grid{gap:6px}.key-instructions{font-size:11px}}
/* Never let the status bar force the remote control beyond a narrow phone viewport. */
.control-deck,.deck-header,.controls{min-width:0;width:100%}
@media(max-width:680px){#gamepadStatus{display:none}}

/* MULTIMANDO v5.3 - En escritorio: conexion e indicadores en UNA sola fila.
   La palanca y la interfaz tactil no cambian. */
@media (min-width: 960px) {
  .app-shell {
    grid-template-columns: minmax(0, 1.48fr) minmax(0, 1fr);
    grid-template-rows: auto auto minmax(0, 1fr) auto;
    column-gap: 8px;
  }
  .app-header,
  .control-deck,
  .app-shell > footer {
    grid-column: 1 / -1;
  }
  .app-header { grid-row: 1; }
  .connect-panel {
    grid-column: 1;
    grid-row: 2;
    min-width: 0;
    min-height: 58px;
    padding: 7px 9px;
    gap: 7px;
  }
  .status-hud {
    grid-column: 2;
    grid-row: 2;
    min-width: 0;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 6px;
  }
  .control-deck { grid-row: 3; }
  .app-shell > footer { grid-row: 4; }
  .nickname-field { gap: 7px; }
  .nickname-field span { font-size: 9px; letter-spacing: .05em; }
  .nickname-field input { min-width: 0; max-width: none; height: 36px; }
  .connect-tools { gap: 5px; }
  .connect-btn, .disconnect-btn { height: 36px; padding: 0 9px; font-size: 10px; }
  .manual-connection summary { min-width: 36px; height: 36px; }
  .manual-label { display: none; }
  .status-hud .stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    padding: 5px 3px;
    text-align: center;
  }
  .status-hud .stat > span { font-size: 8px; letter-spacing: .045em; white-space: nowrap; }
  .status-hud .stat > strong { font-size: clamp(18px, 2vw, 24px); line-height: 1.15; }
  .status-hud .stat > small { display: none; }
}


/* MULTIMANDO v5.4 - Modo AUTO y adaptación fluida de la barra de conexión. */
.auto-choice{display:inline-flex;align-items:center;justify-content:center;gap:6px;height:38px;min-width:76px;padding:0 9px;border:1px solid #3d708d;border-radius:9px;background:#0e263e;color:#c4efff;font-size:10px;font-weight:900;letter-spacing:.08em;white-space:nowrap;cursor:pointer;user-select:none;touch-action:manipulation}
.auto-choice:hover{border-color:var(--cyan);background:#173955}.auto-choice:focus-within{outline:2px solid var(--outline);outline-offset:2px}
.auto-choice input{appearance:none;-webkit-appearance:none;width:16px;height:16px;min-width:16px;border:2px solid #6890a9;border-radius:4px;background:#0a1a31;cursor:pointer;display:grid;place-items:center;margin:0}
.auto-choice input:checked{border-color:#79efff;background:#6fe8ff}.auto-choice input:checked::after{content:'✓';font-size:12px;line-height:1;color:#082338;font-weight:1000}
.auto-choice:has(input:checked){border-color:#52cbdc;background:#0c374a}.auto-choice:has(input:disabled){opacity:.65;cursor:not-allowed}
.auto-choice input:disabled{cursor:not-allowed}
.connect-panel>.manual-popover{position:absolute;z-index:20;right:9px;top:calc(100% + 7px);left:auto;width:min(420px,calc(100vw - 34px));max-width:calc(100vw - 34px);padding:13px;border:1px solid #4e8199;border-radius:11px;background:#0f2a42;box-shadow:0 15px 35px #000c}
.connect-panel>.manual-popover[hidden]{display:none!important}
.connect-panel>.manual-popover label{font-size:10px}
.connect-panel>.manual-popover input{width:100%}
.connect-panel>.manual-popover small{line-height:1.4}
/* 960px+ conserva conexión + 3 indicadores en una única fila */
@media(min-width:960px){
 .app-shell{grid-template-columns:minmax(0,1.46fr) minmax(0,1fr)}
 .connect-panel{grid-template-columns:minmax(0,1fr) auto;gap:7px;min-width:0}
 .nickname-field{min-width:0;gap:7px}
 .nickname-field input{min-width:0;max-width:none;width:100%}
 .connect-tools{flex:none;gap:5px}
 .auto-choice{height:36px;min-width:68px;padding:0 7px;gap:5px;font-size:9px}
 .connect-btn,.disconnect-btn{padding:0 8px}
 .status-hud .stat{min-width:0}
 .status-hud .stat>span{font-size:clamp(7px,.7vw,9px);white-space:nowrap}
}
/* Tabletas: entrada y estados ordenados, botón AUTO claramente visible */
@media(min-width:681px) and (max-width:959px){
 .app-shell{gap:7px}
 .nickname-field input{max-width:none}
 .connect-panel{padding:8px 10px}
 .status-hud .stat{min-width:0}
 .status-hud .stat>strong{font-size:clamp(22px,2.8vw,28px)}
}
@media(max-width:680px){
 .auto-choice{height:36px;min-width:60px;padding:0 6px;gap:4px;font-size:9px}
 .auto-choice input{width:15px;height:15px;min-width:15px}
 .connect-panel>.manual-popover{right:5px;top:calc(100% + 5px);width:calc(100vw - 26px)}
}
/* En móviles muy estrechos, el nombre necesita un renglón propio. */
@media(max-width:359px){
 .connect-panel{grid-template-columns:minmax(0,1fr);gap:5px;padding:6px 7px}
 .nickname-field{width:100%}.nickname-field input{max-width:none;height:30px}
 .connect-tools{justify-content:flex-end;width:100%;gap:6px}
 .auto-choice,.connect-btn,.disconnect-btn{height:30px}
 .connect-tools .auto-choice{margin-right:auto}
 .auto-choice{min-width:67px}
 .connect-panel>.manual-popover{right:3px;width:calc(100vw - 22px)}
}
@media(max-height:560px){.auto-choice{height:31px}.auto-choice input{width:14px;height:14px;min-width:14px}}

/* v5.9: mandos en paisaje, laptops con poca altura, y teclado accesible. */
@media (min-width: 520px) and (max-height: 500px) {
  :root { --stick-size: min(30dvh, 23vw, 126px); }
  .app-shell { gap: 3px; padding: 3px 0; }
  .deck-header { padding: 3px 9px; }
  .deck-footer { padding: 3px 9px; }
  .controls { padding: 2px 4px; gap: 6px; }
  .joystick-zone, .action-zone { gap: 3px; }
  .action-buttons { width: min(100%, 23vw, 174px); gap: 4px; }
  .action-btn { border-width: 2px; font-size: 18px; }
  .aux-btn { height: 24px; }
  .micro-hint { display: none; }
  .control-label { font-size: 8px; }
}

/* MULTIMANDO v6.0: selector y cruceta de cuatro botones; diagonales por arrastre. */
.direction-mode-switch{display:inline-flex;align-items:center;justify-content:center;gap:7px;flex:none;min-height:27px;padding:3px 7px;border:1px solid #355c7c;border-radius:100px;background:#0b1f37;color:#9cb8d2;cursor:pointer;user-select:none;white-space:nowrap}
.mode-name{font-size:9px;font-weight:900;letter-spacing:.065em;color:#85a7c2;transition:color .15s}
.mode-name.selected{color:#6be6ff}
.direction-mode-switch input{position:absolute;width:1px;height:1px;opacity:0;pointer-events:none}
.mode-track{position:relative;display:inline-flex;align-items:center;width:36px;height:18px;flex:none;border-radius:30px;background:#1d4664;border:1px solid #5f9ab6;padding:2px;transition:background .12s}
.mode-knob{display:block;width:12px;height:12px;border-radius:50%;background:#75e5ff;box-shadow:0 0 8px #5abef79a;transition:transform .12s ease}
.direction-mode-switch input:checked + .mode-track{background:#3e3e70;border-color:#9e91e2}
.direction-mode-switch input:checked + .mode-track .mode-knob{background:#d7caff;transform:translateX(17px)}
.direction-mode-switch:focus-within{outline:2px solid #8feeff;outline-offset:2px}
.joystick-frame[hidden],.dpad-frame[hidden]{display:none!important}
.dpad-frame{width:var(--stick-size);height:var(--stick-size);max-width:100%;flex:none;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));grid-template-rows:repeat(3,minmax(0,1fr));gap:3%;padding:4%;align-items:stretch;justify-items:stretch;touch-action:none;user-select:none;position:relative;isolation:isolate;border-radius:24%;border:1px solid #3d6385;background:radial-gradient(circle at 50% 50%,#29415d 5%,#0b1d34 80%);box-shadow:inset 0 0 28px #0008,0 10px 22px #0007}
.dpad-key{display:grid;place-items:center;min-width:0;min-height:0;padding:0;border:1px solid #5b7d9b;border-radius:20%;background:linear-gradient(145deg,#294963,#0d253d);color:#aeeaff;font-size:clamp(15px,2.3vw,27px);font-weight:950;touch-action:none;user-select:none;box-shadow:inset 0 3px 6px #ffffff1a,0 4px 8px #0006}
.dpad-key.pressed,.dpad-key:active{background:linear-gradient(145deg,#54e5ff,#266bb1);color:white;border-color:#a2f5ff;box-shadow:0 0 16px #63ddff88}
.dpad-up{grid-area:1/2}.dpad-left{grid-area:2/1}.dpad-right{grid-area:2/3}.dpad-down{grid-area:3/2}
.dpad-center{grid-area:2/2;display:grid;place-items:center;border-radius:24%;background:#17324d;border:1px solid #3c6981;pointer-events:none}
.dpad-center span{width:29%;height:29%;border-radius:50%;border:2px solid #71d9f7;background:#16334b;box-shadow:0 0 10px #3dd4ff44}
@media(max-width:680px){.direction-mode-switch{padding:2px 5px;gap:5px;min-height:23px}.mode-name{font-size:8px}.mode-track{width:31px;height:16px}.mode-knob{width:10px;height:10px}.direction-mode-switch input:checked + .mode-track .mode-knob{transform:translateX(14px)}.dpad-frame{gap:3%;padding:4%}.dpad-key{font-size:clamp(12px,4.2vw,21px)}}
@media(max-height:560px){.direction-mode-switch{min-height:20px;padding:1px 5px}.mode-name{font-size:8px}.mode-track{height:15px}.mode-knob{width:9px;height:9px}.dpad-frame{border-radius:20%}}
@media(max-width:600px) and (min-height:720px){.direction-mode-switch{min-height:23px}.joystick-zone{gap:4px;margin-top:-14px}.action-zone{margin-top:18px}}

/* v6.0.3: móvil vertical equilibrado: cruceta arriba, botones abajo.
   Ambas zonas siguen en paralelo, incluso en móviles de pantalla alta. */
@media (max-width: 680px) and (orientation: portrait) {
  :root { --stick-size: min(44vw, 26dvh, 205px); }
  .controls {
    grid-template-columns: minmax(0, 1.01fr) minmax(0, .99fr);
    grid-template-rows: minmax(0, 1fr);
    align-items: center;
    align-content: stretch;
    justify-items: stretch;
    gap: clamp(5px, 2vw, 12px);
    padding: 7px 5px;
  }
  .joystick-zone, .action-zone {
    min-width: 0;
    margin-top: 0;
    justify-content: center;
    gap: 5px;
  }
  .joystick-zone { transform: translateY(clamp(-46px, -5.5dvh, -14px)); }
  .action-zone { transform: translateY(clamp(16px, 5.2dvh, 46px)); }
  .dpad-frame, .joystick-frame {
    width: min(100%, var(--stick-size));
    height: auto;
    aspect-ratio: 1;
  }
  .direction-mode-switch { max-width: 100%; gap: 3px; padding: 2px 3px; }
  .mode-name { font-size: clamp(7px, 1.8vw, 9px); letter-spacing: 0; }
  .mode-track { width: 30px; height: 16px; }
  .action-buttons { width: min(100%, 175px); gap: clamp(4px, 1.1vw, 7px); }
  .action-btn { border-width: clamp(2px, .6vw, 3px); font-size: clamp(17px, 4.5vw, 25px); }
  .aux-buttons { gap: 6px; }
  .aux-btn { width: min(47%, 98px); height: clamp(28px, 4.5dvh, 36px); }
  .micro-hint { white-space: normal; text-align: center; max-width: 100%; font-size: clamp(6px, 1.7vw, 8px); }
  .control-label { white-space: normal; text-align: center; font-size: clamp(7px, 2vw, 9px); }
}
/* Ajustes extra para teléfonos muy pequeños, sin ocultar START/SELECT. */
@media (max-width: 680px) and (orientation: portrait) and (max-height: 600px) {
  :root { --stick-size: min(42vw, 25dvh, 160px); }
  .joystick-zone { transform: translateY(-8px); }
  .action-zone { transform: translateY(11px); }
  .joystick-zone, .action-zone { gap: 3px; }
}

/* v6.1.0: tres modos, selector compacto sin sacrificar controles en movil. */
.direction-mode-switch{display:inline-grid;grid-template-columns:repeat(3,max-content);align-items:center;justify-content:center;gap:3px;max-width:100%;min-height:29px;padding:3px;border-radius:10px;cursor:default}
.direction-mode-option{border:1px solid transparent;border-radius:7px;background:transparent;color:#91b8d4;letter-spacing:.018em;font-size:10px;line-height:1.1;font-weight:850;min-width:0;min-height:23px;padding:4px 8px;white-space:nowrap;touch-action:manipulation;user-select:none;transition:background .12s,color .12s,border-color .12s}
.direction-mode-option.selected,.direction-mode-option[aria-pressed="true"]{border-color:#63dff4;background:linear-gradient(135deg,#26597b,#164168);color:#d6faff;box-shadow:0 0 8px #2aa9cf3c}
.direction-mode-option:hover:not(.selected){background:#234360;color:#e5f7ff}
.direction-mode-option:focus-visible{outline:2px solid var(--outline);outline-offset:1px}
@media(max-width:680px){.direction-mode-switch{gap:2px;min-height:25px;padding:2px}.direction-mode-option{font-size:clamp(6px,1.65vw,8.5px);padding:3px clamp(2px,.7vw,5px);min-height:19px;letter-spacing:0}}
@media(max-width:680px) and (orientation:portrait){.direction-mode-switch{gap:1px;padding:2px 1px;max-width:100%}.direction-mode-option{font-size:clamp(6px,1.7vw,8px);padding:3px clamp(2px,.55vw,4px)}}
@media(max-height:560px){.direction-mode-switch{min-height:21px;padding:1px}.direction-mode-option{min-height:17px;padding-top:2px;padding-bottom:2px}}

/* v6.1.1 - SOLO moviles en horizontal: dar prioridad a las zonas de juego.
   Pantallas verticales y escritorio con raton conservan el CSS original. */
@media (orientation: landscape) and (max-height: 520px) and (pointer: coarse) and (hover: none) {
  :root { --stick-size: min(58dvh, 27vw, 200px); }
  html, body { min-height: 0; }
  .app-shell {
    width: calc(100% - 12px);
    height: 100dvh;
    min-height: 0;
    padding: 3px 0;
    gap: 3px;
    display: grid;
    grid-template-columns: minmax(0,1fr);
    grid-template-rows: auto auto minmax(0,1fr);
  }
  /* La cabecera duplicaba informacion ya visible en el panel y quitaba
     espacio tactil. Solo se oculta durante el juego en horizontal movil. */
  .app-header, .app-shell > footer { display: none; }
  .connect-panel {
    grid-column: 1;
    grid-row: 1;
    min-height: 0;
    height: 35px;
    min-width: 0;
    padding: 2px 7px;
    gap: 8px;
    border-radius: 10px;
  }
  .nickname-field { gap: 7px; }
  .nickname-field span { font-size: 9px; }
  .nickname-field input {
    min-width: 0;
    max-width: none;
    width: 100%;
    height: 29px;
  }
  .connect-tools { gap: 5px; flex: none; }
  .auto-choice, .connect-btn, .disconnect-btn {
    min-height: 29px;
    height: 29px;
    padding: 0 8px;
    border-radius: 7px;
    font-size: 9px;
  }
  .auto-choice { min-width: 62px; }
  .status-hud {
    grid-column: 1;
    grid-row: 2;
    min-height: 25px;
    height: 25px;
    min-width: 0;
    gap: 5px;
    grid-template-columns: repeat(3,minmax(0,1fr));
  }
  .status-hud .stat {
    min-width: 0;
    min-height: 0;
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 2px 6px;
    border-radius: 9px;
    text-align: center;
  }
  .status-hud .stat > span {
    display: block;
    min-width: 0;
    font-size: 9px;
    letter-spacing: .02em;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .status-hud .stat > strong {
    display: block;
    flex: none;
    font-size: 16px;
    line-height: 1;
    margin: 0;
    white-space: nowrap;
  }
  .status-hud .stat > small { display: none; }
  .control-deck {
    grid-column: 1;
    grid-row: 3;
    min-height: 0;
    height: 100%;
    border-radius: 12px;
    grid-template-rows: auto minmax(0,1fr) auto;
  }
  .deck-header {
    min-height: 27px;
    height: 27px;
    padding: 2px 9px;
  }
  .deck-title strong { font-size: 10px; }
  .deck-title small { display: none; }
  .deck-badges { gap: 5px; }
  .deck-badges > span:first-child { display: none; }
  .deck-badges > span { padding: 4px 6px; font-size: 8px; }
  .keys-config-btn { height: 23px; min-width: 47px; font-size: 8px; }
  .controls {
    min-height: 0;
    height: 100%;
    grid-template-columns: minmax(0,1fr) minmax(0,1fr);
    grid-template-rows: minmax(0,1fr);
    align-items: center;
    justify-items: center;
    gap: clamp(8px,3vw,26px);
    padding: 2px clamp(5px,2vw,16px);
  }
  .joystick-zone, .action-zone {
    min-height: 0;
    max-height: 100%;
    gap: 3px;
    margin: 0;
    transform: none;
    justify-content: center;
  }
  .direction-mode-switch {
    max-width: 100%;
    min-height: 25px;
    padding: 2px 3px;
    gap: 3px;
  }
  .direction-mode-option {
    min-height: 21px;
    padding: 3px 7px;
    font-size: clamp(8px, 1.25vw, 10px);
  }
  /* El modo ya esta identificado en el selector: evitar otra linea redundante. */
  #directionHint, #modeHelp, .action-zone > .micro-hint { display: none; }
  .joystick-frame, .dpad-frame {
    width: min(100%,var(--stick-size));
    height: auto;
    aspect-ratio: 1 / 1;
    max-height: 100%;
    flex: 0 0 auto;
  }
  .joystick-thumb { min-width: 38px; min-height: 38px; }
  .action-zone > .control-label { font-size: 9px; line-height: 1.1; }
  .action-buttons {
    width: min(100%,78dvh,33vw,270px);
    gap: 5px;
  }
  .action-btn { min-width: 0; border-width: 3px; font-size: clamp(17px,3vw,30px); }
  /* Separacion tactil entre la segunda fila A/B/R y START/SELECT.
     Baja las teclas auxiliares sin invadir el pie ni los botones principales. */
  .aux-buttons { gap: 9px; margin-top: 9px; }
  .aux-btn {
    height: 29px;
    width: min(48%,110px);
    font-size: 9px;
  }
  .deck-footer { min-height: 19px; height: 19px; padding: 2px 8px; }
  .deck-footer p { font-size: 9px; }
  .deck-footer > span:last-child { display: none; }
}
/* Reducir proporcionalmente en telefonos cuya barra del navegador deja muy
   poco alto util. No se aplica a escritorios ni a moviles verticales. */
@media (orientation: landscape) and (max-height: 340px) and (pointer: coarse) and (hover: none) {
  :root { --stick-size: min(53dvh,25vw,165px); }
  .connect-panel { height: 31px; padding: 1px 6px; }
  .nickname-field input, .auto-choice, .connect-btn, .disconnect-btn { height: 27px; min-height: 27px; }
  .status-hud { height: 22px; min-height: 22px; }
  .status-hud .stat > strong { font-size: 14px; }
  .deck-header { height: 25px; min-height: 25px; }
  .deck-footer { height: 16px; min-height: 16px; }
  .direction-mode-switch { min-height: 22px; }
  .direction-mode-option { min-height: 18px; padding: 2px 5px; }
  .action-buttons { width: min(100%,70dvh,31vw,230px); gap: 3px; }
  .aux-buttons { margin-top: 6px; }
  .aux-btn { height: 26px; }
  .action-zone > .control-label { display: none; }
}

/* MULTIMANDO v6.1.5: MIXTO, cruceta tactil con mini joystick central.
   Apariencia diferente del ANALOGICO, sin octagono ni botones flotantes.
   El joystick sigue emitiendo exclusivamente direcciones digitales. */
.joystick-frame .mixed-gate{display:none;pointer-events:none}
.joystick-frame.mixed-mode{
 border:2px solid #456c8d;
 border-radius:23%;
 clip-path:none;
 background:linear-gradient(148deg,#203a56 0%,#0b1e33 48%,#08172a 100%);
 box-shadow:inset 0 2px 2px #b6eff610,inset 0 -7px 22px #0008,0 8px 23px #0007;
}
.joystick-frame.mixed-mode::before{
 content:"";position:absolute;inset:6%;pointer-events:none;
 border:1px solid #5789a433;border-radius:20%;
 background:radial-gradient(circle at center,#1b354a40,transparent 65%);
}
.joystick-frame.mixed-mode.engaged{border-color:#61c6dd;box-shadow:inset 0 0 18px #59d1e31c,0 0 15px #58cef01b,0 8px 23px #0007}
.joystick-frame.mixed-mode .joystick-label,.joystick-frame.mixed-mode .joystick-grid{display:none}
.joystick-frame.mixed-mode .mixed-gate{display:block;position:absolute;inset:0;z-index:1}
/* Cruceta en cruz: las dos piezas forman una sola superficie, no 8 botones. */
.joystick-frame.mixed-mode .mixed-gate::before,
.joystick-frame.mixed-mode .mixed-gate::after{
 content:"";position:absolute;pointer-events:none;z-index:0;
 border:1px solid #547b99;
 background:linear-gradient(142deg,#35526b,#162e48 45%,#0e223b 92%);
 box-shadow:inset 1px 2px 2px #c6f8ff13,inset 0 -4px 10px #0008,0 3px 7px #0005;
}
.joystick-frame.mixed-mode .mixed-gate::before{left:34%;top:9%;width:32%;height:82%;border-radius:19% / 8%}
.joystick-frame.mixed-mode .mixed-gate::after{left:9%;top:34%;width:82%;height:32%;border-radius:8% / 19%}
/* Ocho indicadores finos, integrados en la cruceta. */
.joystick-frame.mixed-mode .mixed-gate>span{
 position:absolute;z-index:2;display:grid;place-items:center;
 width:17%;height:17%;max-width:44px;max-height:44px;
 border:0;border-radius:0;background:transparent;
 color:#84b7d0;font-size:clamp(11px,1.35vw,18px);font-weight:850;
 line-height:1;text-shadow:0 1px 2px #0009;
 box-shadow:none;transition:color .08s,text-shadow .08s,transform .08s;
}
.joystick-frame.mixed-mode .mixed-gate>span.active{
 background:transparent;border:0;box-shadow:none;color:#70edff;
 text-shadow:0 0 9px #62dcf9b3,0 1px 2px #0009;
 transform:scale(1.2)
}
.joystick-frame.mixed-mode .mixed-gate .gate-n{left:41.5%;top:10%}
.joystick-frame.mixed-mode .mixed-gate .gate-s{left:41.5%;bottom:10%}
.joystick-frame.mixed-mode .mixed-gate .gate-w{left:10%;top:41.5%}
.joystick-frame.mixed-mode .mixed-gate .gate-e{right:10%;top:41.5%}
.joystick-frame.mixed-mode .mixed-gate .gate-nw{left:13%;top:13%;font-size:clamp(9px,1.05vw,13px);opacity:.58}
.joystick-frame.mixed-mode .mixed-gate .gate-ne{right:13%;top:13%;font-size:clamp(9px,1.05vw,13px);opacity:.58}
.joystick-frame.mixed-mode .mixed-gate .gate-sw{left:13%;bottom:13%;font-size:clamp(9px,1.05vw,13px);opacity:.58}
.joystick-frame.mixed-mode .mixed-gate .gate-se{right:13%;bottom:13%;font-size:clamp(9px,1.05vw,13px);opacity:.58}
.joystick-frame.mixed-mode .mixed-gate>span.active.gate-nw,
.joystick-frame.mixed-mode .mixed-gate>span.active.gate-ne,
.joystick-frame.mixed-mode .mixed-gate>span.active.gate-sw,
.joystick-frame.mixed-mode .mixed-gate>span.active.gate-se{opacity:1}
/* Mini joystick movil en el centro; no alteramos su posicion calculada por JS. */
.joystick-frame.mixed-mode .joystick-base{z-index:3}
.joystick-frame.mixed-mode .joystick-thumb{
 width:64%;height:64%;border-radius:50%;border:3px solid #81b7c9;
 background:radial-gradient(circle at 29% 21%,#62889e 0%,#31546c 39%,#163149 70%,#0c213a 100%);
 box-shadow:inset 0 0 0 4px #142d41,inset 0 3px 5px #c3faff26,0 5px 13px #000a,0 0 0 2px #071626;
}
.joystick-frame.mixed-mode .thumb-light{
 width:23%;height:23%;border:2px solid #a7f3ff;border-radius:50%;
 background:#317e98;transform:none;box-shadow:0 0 8px #53dcf482;
}
@media(max-width:680px){
 .joystick-frame.mixed-mode .mixed-gate>span{font-size:clamp(12px,3.4vw,17px)}
 .joystick-frame.mixed-mode .mixed-gate .gate-nw,
 .joystick-frame.mixed-mode .mixed-gate .gate-ne,
 .joystick-frame.mixed-mode .mixed-gate .gate-sw,
 .joystick-frame.mixed-mode .mixed-gate .gate-se{font-size:clamp(9px,2.6vw,13px)}
}

/* START / SELECT descienden un poco mas para no interceptar A/B/R.
   En desktop se conserva la posicion original. */
@media (orientation:portrait) and (max-width:680px) and (pointer:coarse){
 .action-zone .aux-buttons{margin-top:clamp(11px,1.6dvh,17px)}
}
@media (orientation:landscape) and (max-height:520px) and (pointer:coarse) and (hover:none){
 .action-zone .aux-buttons{margin-top:16px}
 .deck-footer > span.deck-credit:last-child{display:block;font-size:8px;color:#83cce5;letter-spacing:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:53%;flex:none}
}
@media (orientation:landscape) and (max-height:340px) and (pointer:coarse) and (hover:none){
 .action-zone .aux-buttons{margin-top:11px}
 .deck-footer > span.deck-credit:last-child{font-size:7px;max-width:55%}
}

/* Al agregar el credito como ultimo span, la etiqueta de origen de sala ya
   no es el ultimo hijo. Conservamos su ocultamiento anterior en movil. */
@media(max-width:680px){.deck-footer #connectionSource{display:none}}
@media (orientation:landscape) and (max-height:520px) and (pointer:coarse) and (hover:none){
 .deck-footer #connectionSource{display:none}
}

/* Reconocimiento de la idea en el pie. Se reserva espacio de juego en horizontal
   moviles (donde se muestra dentro de la propia barra de estado). */
.app-shell>footer{display:flex;justify-content:center;align-items:center;flex-wrap:wrap;gap:2px 14px;white-space:normal;overflow:visible;line-height:1.3}
.footer-system{color:#6487a5}
.footer-credit{color:#b8e7ff;font-weight:850;letter-spacing:.025em;white-space:nowrap}
.deck-credit{display:none}
@media (orientation:portrait) and (max-width:680px){
 .app-shell>footer .footer-system{display:none}
 .app-shell>footer .footer-credit{white-space:normal;font-size:9px;line-height:1.2}
}
/* Especificidad: mantener oculta la linea de pie general al girar el telefono. */
@media (orientation:landscape) and (max-height:520px) and (pointer:coarse) and (hover:none){
 .app-shell>footer{display:none}
}

/* Confirmacion de permanencia en cola cada 5 minutos. */
.queue-dialog{position:fixed;inset:0;margin:auto;width:min(420px,calc(100vw - 24px));max-height:calc(100dvh - 22px);padding:0;border:1px solid #426687;border-radius:20px;background:#0d2137;color:#f1f8ff;box-shadow:0 20px 75px #000c;z-index:110;overflow:auto}
.queue-dialog::backdrop{background:rgba(1,8,19,.83);backdrop-filter:blur(6px)}
.queue-dialog-content{display:flex;flex-direction:column;align-items:center;gap:12px;text-align:center;padding:clamp(18px,4vw,30px)}
.queue-dialog-icon{font-size:30px;line-height:1}
.queue-dialog h2{font-size:clamp(17px,4vw,23px);line-height:1.15;margin:0;color:#e5f7ff}
.queue-dialog p{font-size:13px;line-height:1.6;color:#c4d9ec;margin:0}
.queue-dialog-actions{display:flex;width:100%;gap:9px;flex-wrap:wrap}
.queue-dialog-actions button{flex:1 1 155px;min-height:48px;border-radius:10px;border:1px solid #5483a4;font-size:12px;font-weight:800;cursor:pointer;padding:10px 7px}
.queue-dialog-actions .queue-keep{color:#061d2e;background:#76e3c4;border-color:#76e3c4}
.queue-dialog-actions .queue-yield{color:#f6e9f2;background:#243b55;border-color:#58728f}
.queue-dialog small{display:block;color:#8fb0cd;font-size:11px;line-height:1.5}

/* v6.2.0: popup centrado antes de los 10 segundos de activacion. */
.turn-dialog{position:fixed;inset:0;margin:auto;width:min(410px,calc(100vw - 28px));max-height:calc(100dvh - 25px);padding:0;border:1px solid #5092b4;border-radius:22px;background:radial-gradient(circle at top,#1b4268 0%,#0a2039 70%);color:#f5fbff;box-shadow:0 22px 90px #000e;z-index:120;overflow:hidden}
.turn-dialog::backdrop{background:rgba(1,8,20,.82);backdrop-filter:blur(6px)}
.turn-dialog-content{min-height:250px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;text-align:center;padding:25px}
.turn-dialog-icon{font-size:30px}
.turn-dialog h2{margin:0;font-size:clamp(17px,4vw,24px);font-weight:900;letter-spacing:.06em}
.turn-count-number{display:block;font-size:clamp(100px,25vw,158px);font-weight:950;line-height:.95;color:#76f4ff;text-shadow:0 0 24px #5bdcf9aa;animation:turnPulse 1s ease-in-out infinite}
.turn-dialog p{font-size:12px;line-height:1.5;color:#b0d2ec;margin:0}
@keyframes turnPulse{0%,100%{transform:scale(.95);opacity:.9}50%{transform:scale(1.05);opacity:1}}
@media(prefers-reduced-motion:reduce){.turn-count-number{animation:none}}
MULTIMANDO_CSS_FALLBACK;
$cssFile = __DIR__ . '/assets/palanca.css';
if (is_readable($cssFile)) {
    $currentStyle = @file_get_contents($cssFile);
    if (is_string($currentStyle) && trim($currentStyle) !== '') {
        $embeddedStyle = $currentStyle;
    }
}
?>
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#071222">
<meta name="description" content="MULTIMANDO, control remoto web de una sola pantalla. La administración de jugadores y turnos está exclusivamente en Python.">
<title>MULTIMANDO | Control remoto</title>
<!-- CSS included directly to avoid 404, MIME, rewrites, or broken /assets/ paths. -->
<style nonce="<?= htmlspecialchars($styleNonce, ENT_QUOTES, 'UTF-8') ?>"><?= $embeddedStyle ?></style>
<style nonce="<?= htmlspecialchars($styleNonce, ENT_QUOTES, 'UTF-8') ?>">
/* FUTUREO VJOY 2.1 - streaming publico adaptativo, sin requerir turno */
.app-shell{height:auto;min-height:100dvh;grid-template-rows:auto auto auto auto minmax(330px,1fr) auto}
.futureo-stream-panel{min-width:0;display:flex;flex-direction:column;overflow:hidden;gap:0;
 border:1px solid #345c83;border-radius:18px;background:linear-gradient(160deg,#102b49,#07152b);
 box-shadow:0 0 14px #1c9ac020}
.futureo-stream-head{display:flex;justify-content:space-between;align-items:center;gap:12px;
 padding:9px 13px;border-bottom:1px solid #294766}
.futureo-stream-head strong{font-size:clamp(12px,1.8vw,15px);letter-spacing:.08em}
.futureo-stream-badge{font-size:10px;background:#334b63;color:#dce8f4;border-radius:15px;padding:6px 10px;
 font-weight:900;letter-spacing:.05em}
.futureo-live .futureo-stream-badge{background:#a81b37;color:white}
.futureo-stream-media{position:relative;display:grid;place-items:center;overflow:hidden;
 background:#030a13;aspect-ratio:16/9;min-height:0}
.futureo-stream-media img{display:block;object-fit:contain;width:100%;height:100%;max-height:100%}
.futureo-stream-media img[hidden]{display:none}
.futureo-stream-empty{position:absolute;inset:0;display:grid;place-items:center;
 font-size:clamp(13px,2.2vw,21px);color:#799ec4;letter-spacing:.04em;text-align:center;padding:14px;pointer-events:none}
.futureo-stream-media img:not([hidden]) + .futureo-stream-empty{display:none}
.futureo-stream-foot{display:flex;align-items:center;justify-content:space-between;gap:8px;
 padding:9px 12px;color:#a8c6df;font-size:clamp(10px,1.7vw,12px)}
.futureo-stream-foot span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.futureo-stream-expand{border:1px solid #3e7095;background:#142c48;border-radius:8px;
 color:#d9f7ff;padding:7px 10px;font-weight:750}
.futureo-stream-expanded .futureo-stream-media{aspect-ratio:16/9}
.control-deck{min-width:0}
@media(min-width:1000px){
 .app-shell{max-width:1500px;grid-template-columns:minmax(0,1.14fr) minmax(440px,1fr);
  grid-template-rows:auto auto auto minmax(360px,1fr) auto;align-content:start}
 .app-header,.connect-panel,.status-hud,.app-shell>footer{grid-column:1/-1}
 .futureo-stream-panel{grid-column:1;grid-row:4;align-self:start}
 .control-deck{grid-column:2;grid-row:4;align-self:stretch}
 .futureo-stream-media{flex:1;aspect-ratio:16/9}
 .futureo-stream-panel{max-height:calc(100vh - 240px)}
}
@media(max-width:999px){
 .app-shell{grid-template-columns:minmax(0,1fr)}
 .futureo-stream-panel{width:100%}
 .control-deck{min-height:380px}
}
@media(max-width:600px){
 .app-shell{gap:7px;min-height:100dvh;grid-template-rows:auto auto auto auto auto auto}
 .futureo-stream-head{padding:7px 10px}
 .futureo-stream-media{aspect-ratio:16/9}
 .futureo-stream-foot{padding:6px 9px}
 .futureo-stream-media{min-height:140px}
 .control-deck{min-height:310px}
}
</style>
<script src="control.php?v=6.2.0" defer></script>
<script src="assets/futureo-stream.js?v=2.1.0" defer></script>
</head>
<body>
<main class="app-shell">
  <header class="app-header">
    <div class="brand"><div class="brand-mark" aria-hidden="true">M<span class="brand-spark"></span></div>
      <div><strong>MULTIMANDO</strong><small>CONTROL REMOTO WEB</small></div></div>
    <div class="connection-pill" id="connectionPill" role="status"><span class="pulse"></span><span id="connectionText">SIN CONEXIÓN</span></div>
  </header>

  <section class="connect-panel" aria-label="Conectar control remoto">
    <label class="nickname-field"><span>JUGADOR</span><input id="nickname" type="text" maxlength="10" autocomplete="nickname" spellcheck="false" placeholder="Nombre (máx. 10)" aria-label="Nombre del jugador"></label>
    <div class="connect-tools">
      <label class="auto-choice" for="autoRoom" title="Activado: buscar sala usando /api/geturlmultimando">
        <input id="autoRoom" type="checkbox" checked aria-label="Obtener URL automáticamente desde la API">
        <span>AUTO</span>
      </label>
      <button class="connect-btn" type="button" id="connectBtn">CONECTAR</button>
      <button class="disconnect-btn" type="button" id="disconnectBtn" disabled>SALIR</button>
    </div>
    <div class="manual-popover" id="manualRoom" hidden>
      <label for="directUrl">URL MANUAL DEL ANFITRIÓN</label>
      <input id="directUrl" type="url" autocomplete="off" spellcheck="false" inputmode="url" placeholder="https://sala.trycloudflare.com/">
      <small>Desactiva AUTO para escribir la URL de tu sala. Con AUTO marcado se consulta siempre la API.</small>
    </div>
    <p class="error-text" id="connectionError" role="alert" hidden></p>
  </section>

  <section class="status-hud" aria-label="Estado de tu control">
    <div class="stat"><span>MI CONTROL</span><strong id="mySlot">—</strong><small id="myStatus">Sin asignar</small></div>
    <div class="stat"><span>TIEMPO RESTANTE</span><strong class="mono" id="timeLeft">--:--</strong><small id="clockStatus">Definido por el anfitrión</small></div>
    <div class="stat"><span>EN ESPERA</span><strong class="mono" id="queueCount">—</strong><small id="myQueuePosition">Sin conexión</small></div>
  </section>

  <section id="futureoStream" class="futureo-stream-panel" aria-label="Transmision publica del juego" aria-live="off">
    <div class="futureo-stream-head"><strong>● PANTALLA DEL JUEGO</strong><span id="futureoStreamBadge" class="futureo-stream-badge">SIN TRANSMISION</span></div>
    <div class="futureo-stream-media">
      <img id="futureoStreamImage" alt="Imagen en directo de la ventana del juego" hidden decoding="async">
      <div class="futureo-stream-empty">▣<span style="display:block">Esperando imagen del anfitrión</span></div>
    </div>
    <div class="futureo-stream-foot">
      <span id="futureoStreamStatus" role="status">Puedes mirar sin conectarte, sin turno y sin entrar a la cola.</span>
      <button id="futureoStreamSettings" class="futureo-stream-expand" type="button" aria-label="Ampliar imagen">AMPLIAR</button>
    </div>
  </section>

  <section class="control-deck" aria-label="Palanca y botones remotos">
    <div class="deck-header">
      <div class="deck-title"><span class="tiny-led"></span><strong>PALANCA DIGITAL</strong><small id="roomId">SALA —</small></div>
      <div class="deck-badges"><button type="button" class="keys-config-btn" id="openKeys" title="Personalizar teclas del mando">TECLAS</button><span id="gamepadStatus">TECLADO · TÁCTIL</span><span class="slot-indicator" id="slotIndicator">SIN TURNO</span></div>
    </div>
    <div class="controls" id="controllerArea">
      <div class="joystick-zone">
        <div class="direction-mode-switch" id="directionModes" role="group" aria-label="Modo de movimiento">
          <button type="button" class="direction-mode-option selected" data-direction-mode="analog" aria-pressed="true" title="Joystick proporcional">ANALÓGICO</button>
          <button type="button" class="direction-mode-option" data-direction-mode="dpad" aria-pressed="false" title="Cruceta con cuatro botones">CRUCETA</button>
          <button type="button" class="direction-mode-option" data-direction-mode="mixed" aria-pressed="false" title="Cruceta con mini palanca central y ocho direcciones digitales">MIXTO</button>
        </div>
        <span class="control-label" id="directionHint">ANALÓGICO · MOVIMIENTO PROPORCIONAL</span>
        <div class="joystick-frame" id="joystick" tabindex="0" role="application" aria-label="Joystick analógico calibrado; arrastra desde el centro en cualquier dirección">
          <span class="joystick-label north">▲</span><span class="joystick-label east">▶</span><span class="joystick-label south">▼</span><span class="joystick-label west">◀</span>
          <div class="joystick-grid" aria-hidden="true"></div>
          <div class="mixed-gate" aria-hidden="true">
            <span data-rumbo="ar-iz" class="gate-nw">&#8598;</span>
            <span data-rumbo="ar" class="gate-n">&#8593;</span>
            <span data-rumbo="ar-de" class="gate-ne">&#8599;</span>
            <span data-rumbo="iz" class="gate-w">&#8592;</span>
            <span data-rumbo="de" class="gate-e">&#8594;</span>
            <span data-rumbo="ab-iz" class="gate-sw">&#8601;</span>
            <span data-rumbo="ab" class="gate-s">&#8595;</span>
            <span data-rumbo="ab-de" class="gate-se">&#8600;</span>
          </div>
          <div class="joystick-base" aria-hidden="true"><div class="joystick-thumb" id="joystickThumb"><span class="thumb-light"></span></div></div>
        </div>
        <div class="dpad-frame" id="dpad" role="group" aria-label="Cruceta digital: cuatro botones, arrastra para diagonales" hidden>
          <button type="button" class="dpad-key dpad-up" data-pad-dir="ar" aria-label="Arriba">▲</button>
          <button type="button" class="dpad-key dpad-left" data-pad-dir="iz" aria-label="Izquierda">◀</button>
          <span class="dpad-center" aria-hidden="true"><span></span></span>
          <button type="button" class="dpad-key dpad-right" data-pad-dir="de" aria-label="Derecha">▶</button>
          <button type="button" class="dpad-key dpad-down" data-pad-dir="ab" aria-label="Abajo">▼</button>
        </div>
        <span class="micro-hint" id="modeHelp">ZONA MUERTA 14 % · CENTRADO AUTOMÁTICO</span>
      </div>
      <div class="action-zone">
        <span class="control-label">ACCIONES</span>
        <div class="action-buttons" aria-label="Seis botones en dos filas: X Y L arriba y A B R abajo">
          <button class="action-btn btn-x" type="button" data-action="button_x" aria-label="Botón X">X</button>
          <button class="action-btn btn-y" type="button" data-action="button_y" aria-label="Botón Y">Y</button>
          <button class="action-btn btn-l" type="button" data-action="button_lb" aria-label="Botón L">L</button>
          <button class="action-btn btn-a" type="button" data-action="button_a" aria-label="Botón A">A</button>
          <button class="action-btn btn-b" type="button" data-action="button_b" aria-label="Botón B">B</button>
          <button class="action-btn btn-r" type="button" data-action="button_rb" aria-label="Botón R">R</button>
        </div>
        <div class="aux-buttons">
          <button class="aux-btn" type="button" data-action="select" title="SELECT: tecla Retroceso (Backspace)">SELECT</button>
          <button class="aux-btn aux-primary" type="button" data-action="start">START</button>
        </div>
        <span class="micro-hint">WASD · U I O / J K L</span>
      </div>
    </div>
    <div class="deck-footer"><span class="feedback-indicator" aria-hidden="true"></span><p id="feedback" aria-live="polite">Escribe tu nombre y pulsa CONECTAR.</p><span id="connectionSource">API MULTIMANDO</span><span class="deck-credit">Idea original: Bryan Paredes Gracia (FUTUREO - RYANEXX)</span></div>
  </section>
  <dialog id="queueDialog" class="queue-dialog" aria-labelledby="queueDialogTitle" aria-describedby="queueDialogDescription">
    <div class="queue-dialog-content">
      <div class="queue-dialog-icon" aria-hidden="true">⌛</div>
      <h2 id="queueDialogTitle">¿DESEAS SEGUIR ESPERANDO?</h2>
      <p id="queueDialogDescription">Han pasado 5 minutos desde que entraste a la cola o confirmaste tu espera. ¿Quieres mantener tu puesto o cederlo a los demás?</p>
      <div class="queue-dialog-actions">
        <button type="button" id="queueKeepBtn" class="queue-keep">SEGUIR ESPERANDO</button>
        <button type="button" id="queueYieldBtn" class="queue-yield">CEDER MI TURNO</button>
      </div>
      <small>Responde en <strong id="queueResponseLeft">60</strong> segundos. Si no confirmas, saldrás automáticamente de la cola.</small>
    </div>
  </dialog>
  <dialog id="turnDialog" class="turn-dialog" aria-labelledby="turnDialogTitle">
    <div class="turn-dialog-content">
      <div class="turn-dialog-icon" aria-hidden="true">🎮</div>
      <h2 id="turnDialogTitle">¡TU TURNO EMPIEZA EN!</h2>
      <strong id="turnCountdown" class="turn-count-number" aria-live="polite">3</strong>
      <p>Prepara tu mando. Después tendrás 10 segundos para pulsar una tecla.</p>
    </div>
  </dialog>
  <dialog id="keyDialog" class="key-dialog" aria-labelledby="keyDialogTitle">
    <div class="key-dialog-head"><div><strong id="keyDialogTitle">CONFIGURAR TECLAS</strong><small>PERFIL: WASD + U I O / J K L · SELECT = RETROCESO. Los comandos enviados no cambian.</small></div><button type="button" id="closeKeys" class="key-dialog-close" aria-label="Cerrar configuración">CERRAR</button></div>
    <p class="key-instructions">Pulsa una opción y luego la tecla que quieras asignarle. Las asignaciones se guardan en este navegador. RESTAURAR TECLAS activa el perfil predeterminado.</p>
    <div id="keyGrid" class="key-grid" aria-label="Asignación de teclas"></div>
    <p id="keyMessage" class="key-message" role="status">Configuración lista.</p>
    <div class="key-dialog-foot"><button id="resetKeys" type="button">RESTAURAR TECLAS</button><button type="button" id="saveKeys">LISTO</button></div>
  </dialog>
  <footer><span class="footer-system">SOLO CONTROL REMOTO · JUGADORES, COLA Y TURNOS ADMINISTRADOS POR PYTHON</span><span class="footer-credit">Idea original: Bryan Paredes Gracia (FUTUREO - RYANEXX)</span></footer>
</main>
</body>
</html>
