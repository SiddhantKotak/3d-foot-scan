import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

// Interactive WebGL viewer for the reconstructed foot mesh: drag to orbit,
// scroll to zoom. Falls back to a still render if WebGL/the mesh won't load.
export default function FootViewer({
  src,
  poster,
}: {
  src: string;
  poster?: string;
}) {
  const mountRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">(
    "loading",
  );

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const reduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setStatus("error");
      return;
    }

    const width = mount.clientWidth || 480;
    const height = mount.clientHeight || 520;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(width, height);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    mount.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 100000);

    scene.add(new THREE.HemisphereLight(0xffffff, 0x545a52, 1.15));
    const key = new THREE.DirectionalLight(0xffffff, 1.5);
    key.position.set(1, 1.6, 1.4);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0xffe9d8, 0.55);
    rim.position.set(-1.4, 0.6, -1.2);
    scene.add(rim);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.enablePan = false;
    controls.autoRotate = !reduced;
    controls.autoRotateSpeed = 0.7;
    controls.addEventListener("start", () => {
      controls.autoRotate = false;
    });

    let raf = 0;
    let disposed = false;
    let objRadius = 0;

    // Frame the camera to the object's bounding SPHERE, fitting the smaller of
    // the vertical/horizontal FOV, so the foot stays fully in view at every
    // rotation and at any panel aspect ratio. Preserves the current view
    // direction so a resize re-frames without snapping the rotation.
    const frameCamera = () => {
      if (objRadius <= 0) return;
      const vFov = THREE.MathUtils.degToRad(camera.fov);
      const hFov = 2 * Math.atan(Math.tan(vFov / 2) * Math.max(camera.aspect, 1e-4));
      const fitFov = Math.min(vFov, hFov);
      const dist = (objRadius / Math.sin(fitFov / 2)) * 1.15;
      const dir = camera.position.clone();
      if (dir.lengthSq() < 1e-6) dir.set(0.28, -0.9, 0.4);
      dir.normalize();
      camera.position.copy(dir.multiplyScalar(dist));
      camera.near = Math.max(0.01, objRadius / 100);
      camera.far = objRadius * 20;
      camera.updateProjectionMatrix();
      controls.minDistance = objRadius * 1.2;
      controls.maxDistance = objRadius * 8;
      controls.update();
    };

    const loader = new GLTFLoader();
    loader.load(
      src,
      (gltf) => {
        if (disposed) return;
        const obj = gltf.scene;
        const skin = new THREE.MeshStandardMaterial({
          color: 0xc59a80,
          roughness: 0.82,
          metalness: 0.0,
          side: THREE.DoubleSide,
        });
        obj.traverse((c) => {
          const mesh = c as THREE.Mesh;
          if (mesh.isMesh) mesh.material = skin;
        });

        const box = new THREE.Box3().setFromObject(obj);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        obj.position.sub(center);
        scene.add(obj);

        objRadius = 0.5 * size.length();
        // open facing the sole (plantar) so it mirrors the sole capture photo
        camera.position.set(0.28, -0.9, 0.4);
        controls.target.set(0, 0, 0);
        frameCamera();
        setStatus("ready");
      },
      undefined,
      () => {
        if (!disposed) setStatus("error");
      },
    );

    const animate = () => {
      controls.update();
      renderer.render(scene, camera);
      raf = requestAnimationFrame(animate);
    };
    animate();

    const onResize = () => {
      const w = mount.clientWidth;
      const h = mount.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      frameCamera();
    };
    window.addEventListener("resize", onResize);
    const ro = new ResizeObserver(onResize);
    ro.observe(mount);

    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      ro.disconnect();
      controls.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode) {
        renderer.domElement.parentNode.removeChild(renderer.domElement);
      }
    };
  }, [src]);

  return (
    <div className="viewer">
      <div className="viewer__canvas" ref={mountRef} />
      {status === "loading" && (
        <span className="viewer__status mono">Loading 3D mesh…</span>
      )}
      {status === "error" && poster && (
        <img className="viewer__poster" src={poster} alt="Foot reconstruction" />
      )}
      {status === "ready" && (
        <span className="viewer__hint mono">drag to rotate · scroll to zoom</span>
      )}
    </div>
  );
}
