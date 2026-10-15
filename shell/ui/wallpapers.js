/* Wallpaper presets, shared by the desktop, Settings, the setup wizard and the Glass dock.
   `dark: true` means light-coloured text reads best on top of it (used by the Glass menu bar). */
(function () {
  const svg = (s) => 'url("data:image/svg+xml,' + encodeURIComponent(s) + '") center / cover no-repeat';

  // Original artwork: a mountain lake at dusk
  const lake = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#121735"/><stop offset=".32" stop-color="#33295f"/>
      <stop offset=".52" stop-color="#7a3d84"/><stop offset=".62" stop-color="#d0607e"/>
      <stop offset=".68" stop-color="#f6996a"/>
    </linearGradient>
    <radialGradient id="glow" cx="1010" cy="630" r="520" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#ffd9a0" stop-opacity=".95"/><stop offset=".35" stop-color="#ff9a76" stop-opacity=".45"/>
      <stop offset="1" stop-color="#ff7a7a" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="water" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#f3a07c"/><stop offset=".18" stop-color="#b65a83"/>
      <stop offset=".55" stop-color="#3a2d68"/><stop offset="1" stop-color="#0f1230"/>
    </linearGradient>
    <filter id="soft"><feGaussianBlur stdDeviation="5"/></filter>
    <g id="ranges">
      <path d="M0 610 L110 560 L190 585 L300 520 L380 560 L470 500 L560 545 L650 510 L760 570 L860 530 L960 580 L1060 520 L1150 560 L1250 495 L1340 545 L1440 515 L1530 560 L1600 540 L1600 640 L0 640Z" fill="#9b78b0" opacity=".7"/>
      <path d="M0 640 L0 520 L90 470 L170 505 L250 430 L330 480 L420 400 L520 470 L600 455 L690 520 L780 600 L860 640Z" fill="#5d407f"/>
      <path d="M1600 640 L1600 470 L1520 430 L1440 470 L1360 405 L1270 460 L1190 440 L1110 500 L1040 560 L980 640Z" fill="#553a78"/>
      <path d="M0 640 L0 580 L120 560 L240 600 L360 585 L470 620 L560 640Z" fill="#2c2452"/>
      <path d="M1600 640 L1600 590 L1480 575 L1380 600 L1270 590 L1180 625 L1120 640Z" fill="#2a2250"/>
    </g>
  </defs>
  <rect width="1600" height="640" fill="url(#sky)"/>
  <rect width="1600" height="640" fill="url(#glow)"/>
  <g fill="#fff" opacity=".55">
    <circle cx="180" cy="90" r="1.6"/><circle cx="420" cy="160" r="1.2"/><circle cx="640" cy="70" r="1.4"/>
    <circle cx="860" cy="140" r="1"/><circle cx="1120" cy="60" r="1.5"/><circle cx="1340" cy="120" r="1.2"/>
    <circle cx="1500" cy="200" r="1"/><circle cx="300" cy="250" r="1"/><circle cx="1230" cy="230" r="1"/>
  </g>
  <use href="#ranges"/>
  <rect y="640" width="1600" height="360" fill="url(#water)"/>
  <g opacity=".42" filter="url(#soft)" transform="translate(0 1280) scale(1 -1)"><use href="#ranges"/></g>
  <ellipse cx="1010" cy="660" rx="340" ry="26" fill="#ffd2a0" opacity=".35" filter="url(#soft)"/>
  <g fill="#fff" opacity=".12">
    <rect x="760" y="672" width="420" height="2" rx="1"/><rect x="820" y="700" width="300" height="2" rx="1"/>
    <rect x="700" y="735" width="520" height="2" rx="1"/><rect x="880" y="772" width="220" height="2" rx="1"/>
    <rect x="620" y="820" width="640" height="2" rx="1"/>
  </g>
  <path d="M0 1000 L0 900 Q300 860 520 905 T1000 930 T1600 880 L1600 1000Z" fill="#0a0c22" opacity=".85"/>
</svg>`;

  // Original artwork: soft glassy waves
  const liquid = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice">
  <defs>
    <linearGradient id="b" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0b1f4d"/><stop offset=".5" stop-color="#1c4fa8"/><stop offset="1" stop-color="#3fb4e6"/>
    </linearGradient>
    <linearGradient id="w1" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#7fe3ff" stop-opacity=".0"/><stop offset=".5" stop-color="#9ff0ff" stop-opacity=".55"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity=".1"/>
    </linearGradient>
    <filter id="s"><feGaussianBlur stdDeviation="18"/></filter>
  </defs>
  <rect width="1600" height="1000" fill="url(#b)"/>
  <path d="M-100 620 C 250 420, 520 820, 860 600 S 1450 380, 1700 560 L1700 1100 L-100 1100Z" fill="#0e2f74" opacity=".75"/>
  <path d="M-100 560 C 250 360, 520 760, 860 540 S 1450 320, 1700 500" stroke="url(#w1)" stroke-width="70" fill="none" filter="url(#s)"/>
  <path d="M-100 760 C 300 600, 600 940, 980 740 S 1500 600, 1700 720 L1700 1100 L-100 1100Z" fill="#081a45" opacity=".85"/>
  <path d="M-100 700 C 300 540, 600 880, 980 680 S 1500 540, 1700 660" stroke="#b9f3ff" stroke-opacity=".35" stroke-width="26" fill="none" filter="url(#s)"/>
  <circle cx="1260" cy="230" r="220" fill="#8fe1ff" opacity=".18" filter="url(#s)"/>
</svg>`;

  // Original artwork: warm desert dunes
  const dunes = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice">
  <defs>
    <linearGradient id="sk" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffd6a5"/><stop offset=".55" stop-color="#ffb085"/><stop offset="1" stop-color="#f08a6c"/>
    </linearGradient>
  </defs>
  <rect width="1600" height="1000" fill="url(#sk)"/>
  <circle cx="1150" cy="330" r="110" fill="#fff3dc" opacity=".85"/>
  <path d="M0 560 C 260 470, 520 520, 760 600 S 1300 520, 1600 560 L1600 1000 L0 1000Z" fill="#e98a5f"/>
  <path d="M0 680 C 300 600, 640 640, 900 720 S 1360 640, 1600 700 L1600 1000 L0 1000Z" fill="#cf6d4c"/>
  <path d="M0 820 C 340 740, 700 800, 1000 860 S 1400 800, 1600 830 L1600 1000 L0 1000Z" fill="#a8523d"/>
</svg>`;

  window.WALLPAPERS = {
    lake: { name: "Lake at dusk", css: svg(lake), dark: true },
    liquid: { name: "Liquid", css: svg(liquid), dark: true },
    dunes: { name: "Dunes", css: svg(dunes), dark: false },
    meadow: {
      name: "Meadow", dark: false,
      css: "radial-gradient(900px 600px at 20% 25%, #c9e7d8 0%, transparent 60%)," +
           "radial-gradient(800px 700px at 80% 75%, #9fd0c1 0%, transparent 60%)," +
           "radial-gradient(700px 500px at 75% 15%, #e9f2c9 0%, transparent 60%), #b8dccb",
    },
    sky: {
      name: "Sky", dark: false,
      css: "radial-gradient(1000px 700px at 85% 20%, #ffffff 0%, transparent 55%)," +
           "radial-gradient(900px 700px at 10% 90%, #8fb8ff 0%, transparent 60%)," +
           "linear-gradient(160deg, #cfe0ff 0%, #a9c7ff 100%)",
    },
    sunset: {
      name: "Sunset", dark: false,
      css: "radial-gradient(900px 600px at 70% 80%, #ff9e7a 0%, transparent 60%)," +
           "radial-gradient(800px 600px at 20% 20%, #ffd2a8 0%, transparent 60%)," +
           "linear-gradient(170deg, #ffe3c8 0%, #f6a6a0 60%, #b68ad6 100%)",
    },
    lavender: {
      name: "Lavender", dark: false,
      css: "radial-gradient(900px 700px at 25% 70%, #d9c8ff 0%, transparent 60%)," +
           "radial-gradient(800px 600px at 80% 25%, #f6d2f0 0%, transparent 60%), #e6ddfb",
    },
    night: {
      name: "Night", dark: true,
      css: "radial-gradient(1100px 700px at 20% 15%, #24406e 0%, transparent 60%)," +
           "radial-gradient(900px 700px at 85% 80%, #3c2a63 0%, transparent 60%), #0f1422",
    },
    ocean: {
      name: "Deep ocean", dark: true,
      css: "radial-gradient(900px 700px at 70% 30%, #1b6ca8 0%, transparent 60%)," +
           "linear-gradient(200deg, #0a2540 0%, #0f4c75 60%, #0b3b5c 100%)",
    },
  };
  window.wallpaperFor = (key) => window.WALLPAPERS[key] || window.WALLPAPERS[window.__EDITION === "glass" ? "lake" : "meadow"];
})();
