'use client';

import React, { Suspense, useEffect, useRef } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Float, useGLTF } from '@react-three/drei';
import { Mascot, MascotPose } from '../mascot/Mascot';
import { useCan3D } from '@/lib/hooks/useCan3D';
import * as THREE from 'three';

interface Props {
  state?: 'idle' | 'listening' | 'captured' | 'readback' | 'still';
  className?: string;
  fallbackPose?: MascotPose;
}

// Preload the model
useGLTF.preload('/media/3d/MediPilot.glb');

function MascotModel({ state }: { state: Props['state'] }) {
  const { scene } = useGLTF('/media/3d/MediPilot.glb');
  const groupRef = useRef<THREE.Group>(null);

  useEffect(() => {
    if (!groupRef.current) return;
    
    // Very simple state-based transforms on the whole group
    switch (state) {
      case 'listening':
        groupRef.current.rotation.x = 0.2; // lean forward
        groupRef.current.position.y = -0.5;
        break;
      case 'captured':
        groupRef.current.rotation.x = 0.1; 
        groupRef.current.position.y = -0.8;
        break;
      case 'readback':
        groupRef.current.rotation.x = 0;
        groupRef.current.position.y = -1;
        break;
      default: // idle / still
        groupRef.current.rotation.x = 0;
        groupRef.current.rotation.y = 0;
        groupRef.current.position.y = -1;
    }
  }, [state]);

  // Clone the scene so we don't mutate the cached version if used multiple times
  const clonedScene = scene.clone();

  return (
    <group ref={groupRef}>
      <primitive object={clonedScene} scale={2} />
    </group>
  );
}

export default function MascotScene({ state = 'idle', className = '', fallbackPose = 'pose-01' }: Props) {
  const can3D = useCan3D();

  if (!can3D) {
    return (
      <div className={`flex items-center justify-center ${className}`}>
        <Mascot pose={fallbackPose} size={300} />
      </div>
    );
  }

  const isStill = state === 'still';

  return (
    <div className={className}>
      <Canvas camera={{ position: [0, 0, 8], fov: 45 }}>
        <Suspense fallback={null}>
          <Float 
            speed={isStill ? 0 : 2} 
            rotationIntensity={isStill ? 0 : 0.2} 
            floatIntensity={isStill ? 0 : 0.5}
            floatingRange={[-0.2, 0.2]}
          >
            <MascotModel state={state} />
          </Float>
          {/* Bright lighting — key + fill + rim + ambient */}
          <ambientLight intensity={3} />
          <directionalLight position={[5, 10, 5]} intensity={4} />
          <directionalLight position={[-5, 5, -3]} intensity={2} />
          <directionalLight position={[0, -5, 5]} intensity={1.5} color="#C9EBED" />
          <hemisphereLight args={['#ffffff', '#58A6FF', 2]} />
          <OrbitControls 
            enableZoom={false} 
            enablePan={false} 
            enableRotate={true}
            autoRotate={state === 'idle'} 
            autoRotateSpeed={1.0} 
          />
        </Suspense>
      </Canvas>
    </div>
  );
}
