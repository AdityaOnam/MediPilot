'use client';

import React, { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, useGLTF } from '@react-three/drei';
import { useCan3D } from '@/lib/hooks/useCan3D';

interface Props {
  className?: string;
}

useGLTF.preload('/media/3d/kiosk-stand.glb');

function KioskModel() {
  const { scene } = useGLTF('/media/3d/kiosk-stand.glb');
  const clonedScene = scene.clone();
  
  return <primitive object={clonedScene} scale={1.5} position={[0, -2, 0]} />;
}

export default function KioskScene({ className = '' }: Props) {
  const can3D = useCan3D();

  if (!can3D) return null;

  return (
    <div className={className}>
      <Canvas camera={{ position: [0, 2, 8], fov: 45 }}>
        <Suspense fallback={null}>
          <KioskModel />
          <ambientLight intensity={1.5} />
          <directionalLight position={[5, 10, 5]} intensity={2} />
          <OrbitControls 
            enableZoom={false} 
            enablePan={false} 
            enableRotate={true}
            minPolarAngle={Math.PI/3}
            maxPolarAngle={Math.PI/2}
            autoRotate
            autoRotateSpeed={0.3} 
          />
        </Suspense>
      </Canvas>
    </div>
  );
}
