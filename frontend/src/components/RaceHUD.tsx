/**
 * Race HUD - displays checkpoint progress and stage info
 */

import React from 'react';
import type { RaceInfo } from '../game';

interface RaceHUDProps {
  raceInfo: RaceInfo;
}

export const RaceHUD: React.FC<RaceHUDProps> = ({ raceInfo }) => {
  const elapsedTime = raceInfo.finishTime !== null
    ? raceInfo.finishTime
    : (Date.now() / 1000) - raceInfo.startTime;

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 100);
    return `${mins}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
  };

  return (
    <div
      style={{
        position: 'absolute',
        top: 20,
        left: 20,
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
        color: 'white',
        padding: '15px 20px',
        borderRadius: '8px',
        fontFamily: 'monospace',
        fontSize: '14px',
        minWidth: '200px'
      }}
    >
      {/* Stage Progress */}
      <div style={{ marginBottom: '10px' }}>
        <div style={{ fontSize: '12px', color: '#aaa', marginBottom: '4px' }}>
          STAGE PROGRESS
        </div>
        <div style={{ fontSize: '18px', fontWeight: 'bold' }}>
          Checkpoint {raceInfo.currentCheckpoint} / {raceInfo.totalCheckpoints}
        </div>
      </div>

      {/* Progress Bar */}
      <div
        style={{
          width: '100%',
          height: '6px',
          backgroundColor: 'rgba(255, 255, 255, 0.2)',
          borderRadius: '3px',
          marginBottom: '10px',
          overflow: 'hidden'
        }}
      >
        <div
          style={{
            width: `${(raceInfo.currentCheckpoint / raceInfo.totalCheckpoints) * 100}%`,
            height: '100%',
            backgroundColor: '#4CAF50',
            transition: 'width 0.3s ease'
          }}
        />
      </div>

      {/* Time */}
      <div>
        <div style={{ fontSize: '12px', color: '#aaa', marginBottom: '4px' }}>
          {raceInfo.isFinished ? 'FINISH TIME' : 'TIME'}
        </div>
        <div style={{ fontSize: '18px', fontWeight: 'bold', color: raceInfo.isFinished ? '#4CAF50' : 'white' }}>
          {formatTime(elapsedTime)}
        </div>
      </div>

      {/* Finish Message */}
      {raceInfo.isFinished && (
        <div
          style={{
            marginTop: '15px',
            padding: '10px',
            backgroundColor: 'rgba(76, 175, 80, 0.2)',
            borderRadius: '4px',
            textAlign: 'center',
            fontSize: '16px',
            fontWeight: 'bold',
            color: '#4CAF50'
          }}
        >
          STAGE COMPLETE!
        </div>
      )}
    </div>
  );
};
