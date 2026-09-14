import * as THREE from 'three';
import { OrbitControls } from 'three/controls';

const root = document.querySelector('[data-spatial-explorer]');
const data = JSON.parse(document.getElementById('property-scene-data').textContent);
const stage = root.querySelector('[data-scene-stage]');
const host = root.querySelector('[data-scene-canvas]');
const loading = root.querySelector('[data-scene-loading]');
const tooltip = root.querySelector('[data-scene-tooltip]');
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
const money = value => `AED ${Number(value).toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
let selectModel = () => {};

function showZone(code) {
  const zone = data.zones.find(item => item.code === code);
  if (!zone) return;
  root.querySelectorAll('[data-zone]').forEach(link => link.setAttribute('aria-current', String(link.dataset.zone === code)));
  root.querySelector('[data-zone-title]').textContent = `Demo zone ${code}`;
  root.querySelector('[data-zone-description]').textContent = `Synthetic unit-code group · ${zone.occupied} occupied`;
  root.querySelector('[data-zone-records]').textContent = zone.records;
  root.querySelector('[data-zone-occupancy]').textContent = zone.occupancy === null ? '—' : `${zone.occupancy}%`;
  root.querySelector('[data-zone-rent]').textContent = money(zone.annual_rent);
  root.querySelector('[data-zone-report]').href = zone.report_url;
  selectModel(code);
  root.dataset.selectedZone = code;
}

root.querySelectorAll('[data-zone]').forEach(link => link.addEventListener('click', event => {
  // Keep modified clicks available for opening the zone report in another tab.
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  showZone(link.dataset.zone);
}));

function unavailable() {
  loading.hidden = true;
  root.dataset.sceneState = 'unavailable';
  root.querySelector('[data-scene-fallback]').hidden = false;
  root.querySelector('[data-scene-error]').hidden = false;
  root.querySelectorAll('[data-view], [data-scene-action]').forEach(button => {
    if (button.dataset.sceneAction !== 'expand') button.disabled = true;
  });
}

// This also supplies a usable photo/report fallback if a module fails to load.
const loadTimeout = setTimeout(() => { if (!root.dataset.sceneState) unavailable(); }, 15000);

try { initialize(); } catch (error) { unavailable(); }

function initialize() {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#e3ece8');
  scene.fog = new THREE.Fog('#e3ece8', 270, 560);
  const camera = new THREE.PerspectiveCamera(35, 1, 1, 800);
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'low-power' });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.7));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.3;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  host.appendChild(renderer.domElement);
  renderer.domElement.tabIndex = 0;
  renderer.domElement.setAttribute('aria-label', `${data.name} illustrative 3D property. Arrow keys rotate, plus and minus zoom. Use the zone buttons to select buildings.`);
  renderer.domElement.setAttribute('role', 'img');
  renderer.domElement.addEventListener('webglcontextlost', event => { event.preventDefault(); unavailable(); });

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.09;
  controls.enablePan = false;
  controls.minDistance = 85;
  controls.maxDistance = 330;
  controls.minPolarAngle = 0.04;
  controls.maxPolarAngle = Math.PI * 0.47;
  controls.autoRotateSpeed = 0.35;
  const isTall = ['gate', 'the-bridges-ii'].includes(data.slug);
  const targetHeight = isTall ? 12 : 7;
  const home = new THREE.Vector3(145, isTall ? 135 : 122, 155);
  controls.target.set(0, targetHeight, 0);
  camera.position.copy(home);
  controls.update();

  const ambient = new THREE.HemisphereLight('#eff7ff', '#87917a', 2.1);
  scene.add(ambient);
  const sun = new THREE.DirectionalLight('#fff2d3', 3.7);
  sun.position.set(-75, 130, 65);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -115, right: 115, top: 115, bottom: -115, near: 1, far: 320 });
  sun.shadow.normalBias = 0.15;
  sun.shadow.bias = -0.0001;
  sun.shadow.radius = 4;
  scene.add(sun);
  const fill = new THREE.DirectionalLight('#cfedec', 1.2);
  fill.position.set(80, 60, -90);
  scene.add(fill);

  const material = (color, extra = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.75, ...extra });
  const mats = {
    stone: material('#e5decb'), ivory: material('#f5efdd'), trim: material('#f1e9d4'),
    glass: material('#477178', { metalness: 0.35, roughness: 0.28 }),
    roof: material('#bbbaa6'), road: material('#8a9790'), marking: material('#d6d9c8'),
    pavement: material('#d5cdb6'), lawn: material('#8ea68a'), darkLawn: material('#708f72'),
    leaf: material('#487b61'), leafLight: material('#779667'), trunk: material('#9b8765'),
    gold: material('#b69456', { metalness: 0.3, roughness: 0.4 }), white: material('#f8f1de'),
    water: material('#579b9b', { roughness: 0.24, metalness: 0.25 }),
    pool: material('#5fb4b5', { roughness: 0.18, metalness: 0.15 }),
    selected: material('#d8b774', { emissive: '#a07830', emissiveIntensity: 0.16 }),
  };
  const unitBox = new THREE.BoxGeometry(1, 1, 1);
  const unitCylinder = new THREE.CylinderGeometry(1, 1, 1, 8);
  const unitSphere = new THREE.IcosahedronGeometry(1, 1);
  const decoration = [];
  const pickables = [];
  const zoneMeshes = new Map();
  const model = new THREE.Group();
  scene.add(model);

  function mesh(geometry, mat, parent = model) {
    const object = new THREE.Mesh(geometry, mat);
    object.castShadow = true;
    object.receiveShadow = true;
    parent.add(object);
    return object;
  }
  function box(x, y, z, width, height, depth, mat, zone = null) {
    const object = mesh(unitBox, mat);
    object.position.set(x, y, z);
    object.scale.set(width, height, depth);
    if (zone) {
      object.userData.zone = zone;
      object.userData.originalMaterial = mat;
      pickables.push(object);
      if (!zoneMeshes.has(zone)) zoneMeshes.set(zone, []);
      zoneMeshes.get(zone).push(object);
    } else decoration.push(object);
    return object;
  }
  function foliage(x, y, z, size, mat = mats.leaf) {
    const crown = mesh(unitSphere, mat);
    crown.position.set(x, y, z);
    crown.scale.set(size, size * 0.83, size);
    decoration.push(crown);
  }
  function tree(x, z, palm = false, base = 0.7) {
    const height = palm ? 6.1 : 3.6;
    const trunk = mesh(unitCylinder, mats.trunk);
    trunk.position.set(x, base + height / 2, z);
    trunk.scale.set(palm ? 0.22 : 0.28, height, palm ? 0.22 : 0.28);
    decoration.push(trunk);
    if (palm) {
      for (let i = 0; i < 7; i++) {
        const angle = i / 7 * Math.PI * 2;
        const leaf = mesh(unitSphere, i % 2 ? mats.leafLight : mats.leaf);
        leaf.position.set(x + Math.cos(angle) * 1.2, base + height, z + Math.sin(angle) * 1.2);
        leaf.scale.set(2.5, 0.24, 0.6);
        leaf.rotation.set(0, -angle, 0.12);
        decoration.push(leaf);
      }
    } else foliage(x, base + height, z, 2.3);
  }
  function pool(x, z, width = 14, depth = 6, y = 0.8) {
    box(x, y, z, width + 1.4, 0.25, depth + 1.4, mats.ivory);
    box(x, y + 0.16, z, width, 0.12, depth, mats.pool);
    for (let i = -1; i <= 1; i++) box(x + i * 3, y + 0.3, z + depth / 2 + 1.7, 1.1, 0.22, 2, mats.white);
  }
  function building(x, z, width, depth, height, code, style = 'terrace') {
    const base = 1.05;
    box(x, base + height / 2, z, width, height, depth, mats.stone, code);
    const floors = Math.max(2, Math.round(height / 3.2));
    for (let f = 0; f < floors; f++) {
      const y = base + 1.7 + f * (height / floors);
      box(x, y, z + depth / 2 + 0.08, width - 1.3, 1.85, 0.18, mats.glass);
      box(x, y, z - depth / 2 - 0.08, width - 1.3, 1.85, 0.18, mats.glass);
      box(x - width / 2 - 0.08, y, z, 0.18, 1.85, depth - 1.1, mats.glass);
      box(x + width / 2 + 0.08, y, z, 0.18, 1.85, depth - 1.1, mats.glass);
      box(x, y + 1.22, z, width + 0.85, 0.25, depth + 0.85, mats.trim);
    }
    for (let sx = -width / 2 + 0.4; sx <= width / 2; sx += 4) {
      box(x + sx, base + height / 2, z + depth / 2 + 0.24, 0.34, height, 0.38, mats.ivory);
      box(x + sx, base + height / 2, z - depth / 2 - 0.24, 0.34, height, 0.38, mats.ivory);
    }
    box(x, base + height + 0.3, z, width + 1.1, 0.6, depth + 1.1, mats.ivory);
    box(x, base + height + 0.63, z, width - 1.5, 0.12, depth - 1.5, mats.roof);
    if (style === 'terrace') {
      box(x - width * 0.16, base + height + 1.6, z, width * 0.48, 2.1, depth * 0.55, mats.ivory, code);
      box(x + width * 0.29, base + height + 0.85, z, width * 0.2, 0.25, depth * 0.55, mats.lawn);
      for (let i = -2; i <= 2; i++) box(x + i * 1.4 - width * 0.15, base + height + 3, z, 0.32, 0.18, depth * 0.62, mats.gold);
    } else {
      box(x, base + height + 1.3, z, width * 0.45, 1.3, depth * 0.4, mats.roof);
    }
    // Entry canopy and a pedestrian forecourt.
    box(x, 3.6, z + depth / 2 + 1.6, 5, 0.3, 3, mats.gold);
    box(x, 0.82, z + depth / 2 + 3, width + 3, 0.16, 4, mats.pavement);
  }
  function roundedPlate(width, depth, thickness, mat, y) {
    const x = -width / 2, z = -depth / 2, r = 3;
    const shape = new THREE.Shape();
    shape.moveTo(x + r, z); shape.lineTo(x + width - r, z); shape.quadraticCurveTo(x + width, z, x + width, z + r);
    shape.lineTo(x + width, z + depth - r); shape.quadraticCurveTo(x + width, z + depth, x + width - r, z + depth);
    shape.lineTo(x + r, z + depth); shape.quadraticCurveTo(x, z + depth, x, z + depth - r);
    shape.lineTo(x, z + r); shape.quadraticCurveTo(x, z, x + r, z);
    const plate = mesh(new THREE.ExtrudeGeometry(shape, { depth: thickness, bevelEnabled: false, curveSegments: 6 }), mat);
    plate.rotation.x = -Math.PI / 2;
    plate.position.y = y;
  }

  const ground = mesh(new THREE.PlaneGeometry(1500, 1500), material('#d9e4dc'), scene);
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -5;
  ground.castShadow = false;
  roundedPlate(142, 116, 4, material('#8c9d91'), -4);
  roundedPlate(143, 117, 0.7, mats.ivory, -0.2);
  roundedPlate(140, 114, 0.3, mats.pavement, 0.5);
  const waterfront = ['eastern-mangroves', 'the-bridges-ii', 'arc'].includes(data.slug);
  box(0, 0.82, waterfront ? -13 : -1, 127, 0.14, waterfront ? 72 : 98, mats.lawn);
  // Perimeter road, center walk and fine road markings.
  box(0, 0.96, -46, 131, 0.15, 5, mats.road);
  box(-63, 0.96, -4, 5, 0.15, 83, mats.road);
  box(63, 0.96, -4, 5, 0.15, 83, mats.road);
  box(0, 0.99, -4, 4, 0.15, 77, mats.pavement);
  for (let x = -58; x < 60; x += 9) box(x, 1.05, -46, 4, 0.03, 0.17, mats.marking);
  for (let i = 0; i < 13; i++) {
    tree(-57 + i * 9.4, -39, i % 3 !== 0);
    if (i % 2 === 0) {
      const car = box(-55 + i * 8, 1.65, -46, 3.5, 1.2, 1.5, i % 4 ? mats.white : mats.glass);
      box(car.position.x, 2.3, -46, 1.7, 0.5, 1.25, mats.glass);
    }
  }
  if (waterfront) {
    box(0, 0.91, 38, 138, 0.12, 34, mats.water);
    box(0, 1.04, 23, 137, 0.25, 4.5, mats.ivory);
    for (let x = -57; x <= 58; x += 10) tree(x, 21, true);
    for (let row = 0; row < 7; row++) {
      const points = [];
      for (let x = -68; x <= 68; x += 2) points.push(new THREE.Vector3(x, 1.02, 28 + row * 4 + Math.sin(x / 6 + row) * 0.5));
      const wave = new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), new THREE.LineBasicMaterial({ color: '#bcded4', transparent: true, opacity: 0.3 }));
      model.add(wave);
    }
    if (data.slug === 'eastern-mangroves') {
      for (let i = 0; i < 37; i++) foliage(-65 + i * 3.6, 2.1, 49 + Math.sin(i * 1.9) * 2.1, 2.3 + (i % 3) * 0.5, i % 2 ? mats.leaf : mats.leafLight);
      for (const x of [-37, 23]) {
        box(x, 1.25, 30, 2.3, 0.5, 14, mats.pavement);
        const hull = mesh(new THREE.CapsuleGeometry(1.3, 4, 3, 8), mats.white);
        hull.rotation.x = Math.PI / 2; hull.position.set(x + 4, 1.9, 34); hull.scale.z = 0.5;
        box(x + 4, 2.7, 34, 1.6, 1, 2.8, mats.ivory);
        box(x + 4, 3.24, 34, 1.4, 0.12, 1.6, mats.glass);
      }
    }
  } else {
    box(0, 0.95, 45, 130, 0.15, 5, mats.road);
    for (let x = -58; x < 60; x += 9) { box(x, 1.05, 45, 4, 0.03, 0.17, mats.marking); tree(x, 37, true); }
  }

  const codes = data.zones.map(zone => zone.code);
  const centers = new Map();
  if (data.slug === 'gate') {
    for (let i = 0; i < 3; i++) {
      const x = (i - 1) * 35;
      building(x, -19, 18, 19, 61, codes[i], 'tower');
      centers.set(codes[i], new THREE.Vector3(x, 38, -19));
      building(x, 15, 25, 14, 13 + i % 2 * 5, codes[i + 3]);
      centers.set(codes[i + 3], new THREE.Vector3(x, 12, 15));
    }
    box(0, 63.8, -19, 92, 4.3, 23, mats.ivory);
    box(0, 66.05, -19, 87, 0.25, 18, mats.lawn);
    pool(0, -18, 24, 7, 66.3);
  } else if (data.slug === 'arc') {
    for (let i = 0; i < 6; i++) {
      const start = Math.PI * (0.06 + i * 0.145), end = start + Math.PI * 0.135;
      const shape = new THREE.Shape();
      shape.absarc(0, 0, 43, start, end, false);
      shape.absarc(0, 0, 29, end, start, true); shape.closePath();
      const height = 21 + (i % 2) * 3;
      const body = mesh(new THREE.ExtrudeGeometry(shape, { depth: height, bevelEnabled: false, curveSegments: 24 }), mats.stone);
      body.rotation.x = -Math.PI / 2; body.position.set(0, 1, 9);
      body.userData.zone = codes[i]; body.userData.originalMaterial = mats.stone;
      pickables.push(body); zoneMeshes.set(codes[i], [body]);
      centers.set(codes[i], new THREE.Vector3(Math.cos((start + end) / 2) * 36, 14, 9 - Math.sin((start + end) / 2) * 36));
      const bandShape = new THREE.Shape();
      bandShape.absarc(0, 0, 43.4, start, end, false);
      bandShape.absarc(0, 0, 28.6, end, start, true); bandShape.closePath();
      for (let floor = 1; floor <= Math.floor(height / 3); floor++) {
        const band = mesh(new THREE.ExtrudeGeometry(bandShape, { depth: 0.45, bevelEnabled: false, curveSegments: 24 }), mats.ivory);
        band.rotation.x = -Math.PI / 2; band.position.set(0, floor * 3 + 1, 9);
      }
      for (let col = 0; col < 7; col++) {
        const angle = start + (end - start) * (col + 0.5) / 7;
        const window = box(Math.cos(angle) * 43.08, height / 2 + 1, 9 - Math.sin(angle) * 43.08, 1.3, height - 2, 0.16, mats.glass);
        window.rotation.y = angle - Math.PI / 2;
        const innerWindow = box(Math.cos(angle) * 28.92, height / 2 + 1, 9 - Math.sin(angle) * 28.92, 1.25, height - 2, 0.16, mats.glass);
        innerWindow.rotation.y = angle - Math.PI / 2;
      }
    }
    pool(0, -1, 28, 9);
    for (const x of [-20, 20]) { tree(x, 8, true); tree(x, -8, true); }
  } else if (data.slug === 'sas-al-nakhl') {
    codes.forEach((code, i) => {
      const x = (i % 3 - 1) * 38, z = i < 3 ? -23 : 13;
      centers.set(code, new THREE.Vector3(x, 5, z));
      box(x, 0.95, z, 33, 0.1, 29, mats.darkLawn);
      for (const dx of [-8, 8]) for (const dz of [-7, 7]) {
        building(x + dx, z + dz, 10, 8, 6.4, code, 'villa');
        box(x + dx + 2, 8.3, z + dz, 5, 2.8, 6, mats.ivory, code);
      }
      tree(x, z, true); tree(x - 15, z + 10); tree(x + 15, z - 10);
    });
  } else {
    codes.forEach((code, i) => {
      const x = (i % 3 - 1) * 39, z = i < 3 ? -23 : (waterfront ? 5 : 13);
      const tall = data.slug === 'the-bridges-ii';
      const height = tall ? [39, 47, 42, 42, 45, 38][i] : [19, 25, 20, 14, 19, 15][i];
      building(x, z, tall ? 15 : 25, tall ? 16 : 12, height, code, tall ? 'tower' : 'terrace');
      centers.set(code, new THREE.Vector3(x, height * 0.6, z));
      tree(x - 15, z, true); tree(x + 15, z + 3, true);
      if (data.slug === 'al-rayyana') {
        building(x - 8, z + 9, 9, 9, height - 4, code);
        pool(x + 8, z + 12, 8, 5);
      }
    });
    if (waterfront) { pool(-19, -9, 8, 6); pool(20, -9, 8, 6); }
  }

  // Merge repeated facade, tree and landscape geometry into GPU instances.
  // The six selectable zone bodies stay separate for picking and highlighting.
  model.updateMatrixWorld(true);
  const batches = new Map();
  decoration.forEach(object => {
    const key = `${object.geometry.uuid}:${object.material.uuid}`;
    if (!batches.has(key)) batches.set(key, { geometry: object.geometry, material: object.material, matrices: [] });
    batches.get(key).matrices.push(object.matrixWorld.clone());
    object.removeFromParent();
  });
  batches.forEach(batch => {
    const instances = new THREE.InstancedMesh(batch.geometry, batch.material, batch.matrices.length);
    batch.matrices.forEach((matrix, i) => instances.setMatrixAt(i, matrix));
    instances.castShadow = true; instances.receiveShadow = true;
    instances.computeBoundingSphere();
    scene.add(instances);
  });

  const halo = mesh(new THREE.RingGeometry(3.9, 4.3, 40), new THREE.MeshBasicMaterial({ color: '#ceaa67', side: THREE.DoubleSide, depthTest: false }), scene);
  halo.rotation.x = -Math.PI / 2;
  halo.renderOrder = 5;
  halo.visible = false;
  let selected = null;
  let hovered = null;
  let visible = true;
  let frames = 2;
  let golden = false;
  const invalidate = () => { frames = 35; };
  selectModel = code => {
    selected = code;
    zoneMeshes.forEach((meshes, zone) => meshes.forEach(object => { object.material = zone === selected ? mats.selected : object.userData.originalMaterial; }));
    const center = centers.get(code);
    if (center) { halo.position.set(center.x, 1.4, center.z); halo.visible = true; }
    invalidate();
  };
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  function pick(event) {
    const bounds = renderer.domElement.getBoundingClientRect();
    pointer.set((event.clientX - bounds.left) / bounds.width * 2 - 1, -(event.clientY - bounds.top) / bounds.height * 2 + 1);
    raycaster.setFromCamera(pointer, camera);
    return raycaster.intersectObjects(pickables, false)[0]?.object.userData.zone;
  }
  let down = null;
  renderer.domElement.addEventListener('pointerdown', event => { down = { x: event.clientX, y: event.clientY, id: event.pointerId }; });
  renderer.domElement.addEventListener('pointerup', event => {
    if (down && down.id === event.pointerId && Math.hypot(event.clientX - down.x, event.clientY - down.y) < 5) {
      const code = pick(event); if (code) showZone(code);
    }
    down = null;
  });
  renderer.domElement.addEventListener('pointercancel', () => { down = null; });
  renderer.domElement.addEventListener('pointermove', event => {
    if (event.buttons || event.pointerType === 'touch') { tooltip.hidden = true; return; }
    const code = pick(event);
    if (hovered !== code) {
      hovered = code;
      renderer.domElement.style.cursor = code ? 'pointer' : 'grab';
      zoneMeshes.forEach((meshes, zone) => meshes.forEach(object => { object.material = zone === selected || zone === code ? mats.selected : object.userData.originalMaterial; }));
      invalidate();
    }
    tooltip.hidden = !code;
    if (code) {
      const rect = stage.getBoundingClientRect();
      tooltip.textContent = `Zone ${code} · ${data.zones.find(zone => zone.code === code).records} demo records`;
      tooltip.style.left = `${Math.max(8, Math.min(event.clientX - rect.left + 15, rect.width - 200))}px`;
      tooltip.style.top = `${Math.max(8, Math.min(event.clientY - rect.top - 35, rect.height - 50))}px`;
    }
  });
  renderer.domElement.addEventListener('pointerleave', () => {
    hovered = null; tooltip.hidden = true;
    zoneMeshes.forEach((meshes, zone) => meshes.forEach(object => { object.material = zone === selected ? mats.selected : object.userData.originalMaterial; }));
    invalidate();
  });
  function setOrbit(enabled) {
    controls.autoRotate = enabled;
    root.querySelector('[data-scene-action=orbit]').setAttribute('aria-pressed', String(enabled));
    invalidate();
  }
  controls.addEventListener('start', () => { setOrbit(false); tooltip.hidden = true; });
  controls.addEventListener('change', invalidate);
  function view(mode) {
    setOrbit(false);
    controls.target.set(0, targetHeight, 0);
    camera.position.copy(mode === 'top' ? new THREE.Vector3(0, camera.aspect < 1.1 ? 275 : 235, 0.1) : controls.target.clone().add(home.clone().normalize().multiplyScalar(camera.aspect < 1.1 ? 330 : home.length())));
    controls.update();
    root.dataset.cameraView = mode;
    root.querySelectorAll('[data-view]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.view === mode)));
    invalidate();
  }
  function zoom(factor) {
    const offset = camera.position.clone().sub(controls.target);
    offset.setLength(THREE.MathUtils.clamp(offset.length() * factor, controls.minDistance, controls.maxDistance));
    camera.position.copy(controls.target).add(offset); controls.update(); invalidate();
  }
  root.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => view(button.dataset.view)));
  root.querySelectorAll('[data-scene-action]').forEach(button => button.addEventListener('click', () => {
    switch (button.dataset.sceneAction) {
      case 'in': zoom(0.84); break;
      case 'out': zoom(1.19); break;
      case 'reset': view('perspective'); break;
      case 'orbit': setOrbit(!controls.autoRotate); break;
      case 'light':
        golden = !golden;
        sun.color.set(golden ? '#ffcb88' : '#fff2d3');
        sun.position.set(golden ? -120 : -75, golden ? 65 : 130, 65);
        ambient.intensity = golden ? 1.4 : 2.1;
        scene.background.set(golden ? '#e9dfcb' : '#e3ece8');
        scene.fog.color.copy(scene.background);
        ground.material.color.set(golden ? '#d8ccaf' : '#d9e4dc');
        mats.glass.emissive.set(golden ? '#dfa15c' : '#000000');
        mats.glass.emissiveIntensity = golden ? 0.2 : 0;
        button.setAttribute('aria-pressed', String(golden));
        button.setAttribute('aria-label', golden ? 'Switch to daylight' : 'Switch to golden hour');
        button.title = button.getAttribute('aria-label');
        root.dataset.lighting = golden ? 'golden' : 'day';
        invalidate(); break;
    }
  }));
  renderer.domElement.addEventListener('keydown', event => {
    if (['+', '=', '-', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
      event.preventDefault(); setOrbit(false);
      if (['+', '=', '-'].includes(event.key)) zoom(event.key === '-' ? 1.15 : 0.87);
      else {
        const sphere = new THREE.Spherical().setFromVector3(camera.position.clone().sub(controls.target));
        sphere.theta += event.key === 'ArrowLeft' ? 0.12 : event.key === 'ArrowRight' ? -0.12 : 0;
        sphere.phi = THREE.MathUtils.clamp(sphere.phi + (event.key === 'ArrowUp' ? -0.1 : event.key === 'ArrowDown' ? 0.1 : 0), controls.minPolarAngle, controls.maxPolarAngle);
        camera.position.setFromSpherical(sphere).add(controls.target); controls.update(); invalidate();
      }
    }
  });
  const resize = new ResizeObserver(() => {
    const { width, height } = host.getBoundingClientRect();
    if (!width || !height) return;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
    // A narrow viewport needs more camera distance to frame the entire diorama.
    const distance = width / height < 1.1 ? 330 : home.length();
    if (!root.dataset.selectedZone) camera.position.copy(controls.target).add(home.clone().normalize().multiplyScalar(distance));
    controls.update(); invalidate();
  });
  resize.observe(host);
  const observer = new IntersectionObserver(entries => { visible = entries[0].isIntersecting; if (visible) invalidate(); }, { threshold: 0.01 });
  observer.observe(stage);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) invalidate(); });
  let previousTime = 0;
  renderer.setAnimationLoop(time => {
    const delta = Math.min((time - previousTime) / 1000, 0.05); previousTime = time;
    if (!visible || document.hidden || root.dataset.sceneState === 'unavailable') return;
    if (controls.autoRotate || frames > 0) {
      controls.update(delta);
      renderer.render(scene, camera);
      frames--;
    }
  });
  if (reducedMotion) controls.enableDamping = false;
  root.dataset.sceneState = 'ready';
  root.dataset.sceneStyle = data.slug;
  root.querySelectorAll('[data-view], [data-scene-action]').forEach(button => { button.disabled = false; });
  root.querySelector('[data-scene-error]').hidden = true;
  loading.hidden = true;
  root.querySelector('[data-scene-fallback]').hidden = true;
  clearTimeout(loadTimeout);
  window.addEventListener('pagehide', event => {
    if (event.persisted) return;
    renderer.setAnimationLoop(null); controls.dispose(); resize.disconnect(); observer.disconnect();
    scene.traverse(object => { object.geometry?.dispose(); });
    new Set([...Object.values(mats), ground.material, halo.material]).forEach(mat => mat.dispose());
    renderer.dispose();
  }, { once: true });
}

// Expanded mode also works without the Fullscreen API (including mobile Safari).
const expandButton = root.querySelector('[data-scene-action=expand]');
let previousOverflow = '';
function expand(enabled) {
  if (enabled) previousOverflow = document.body.style.overflow;
  root.classList.toggle('is-expanded', enabled);
  expandButton.setAttribute('aria-expanded', String(enabled));
  expandButton.setAttribute('aria-label', enabled ? 'Close expanded 3D view' : 'Expand 3D view');
  document.body.style.overflow = enabled ? 'hidden' : previousOverflow;
  if (enabled) { root.setAttribute('role', 'dialog'); root.setAttribute('aria-modal', 'true'); }
  else { root.removeAttribute('role'); root.removeAttribute('aria-modal'); }
  expandButton.focus();
}
expandButton.addEventListener('click', () => expand(!root.classList.contains('is-expanded')));
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && root.classList.contains('is-expanded')) expand(false);
  if (event.key === 'Tab' && root.classList.contains('is-expanded')) {
    const targets = [...root.querySelectorAll('a[href], button:not(:disabled), [tabindex="0"]')].filter(element => element.getClientRects().length);
    const first = targets[0], last = targets[targets.length - 1];
    if (event.shiftKey && (document.activeElement === first || !root.contains(document.activeElement))) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && (document.activeElement === last || !root.contains(document.activeElement))) { event.preventDefault(); first.focus(); }
  }
});
