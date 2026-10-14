import * as THREE from 'three';
const host = document.getElementById('host');
const r = new THREE.WebGLRenderer({antialias:true}); r.setSize(host.clientWidth, host.clientHeight); host.appendChild(r.domElement);
const s = new THREE.Scene(); const c = new THREE.PerspectiveCamera(50, host.clientWidth/host.clientHeight, 0.1, 100); c.position.set(0,1,4);
s.add(new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshNormalMaterial()));
window.__ready = Promise.resolve();
window.__renderAt = async (T) => { r.render(s,c); console.warn(r.capabilities.isWebGL2, r.getContext().getParameter(r.getContext().RENDERER)); };
