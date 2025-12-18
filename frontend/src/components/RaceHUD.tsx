/**
 * Race HUD - displays checkpoint progress and stage info
 */

import React from 'react';
import type { RaceInfo, CarState } from '../game';

interface RaceHUDProps {
  raceInfo: RaceInfo;
  car?: CarState;  // Optional car state for off-track indicator
}

export const RaceHUD: React.FC<RaceHUDProps> = ({ raceInfo, car }) => {
  // Calculate elapsed time correctly based on race state
  const calculateElapsedTime = (): number => {
    // If race finished, calculate elapsed time from start to finish
    if (raceInfo.isFinished && raceInfo.finishTime !== null && raceInfo.startTime) {
      // finishTime and startTime are both absolute timestamps
      // Calculate the elapsed time between them
      return raceInfo.finishTime - raceInfo.startTime;
    }

    // If race hasn't started yet, show 0
    if (!raceInfo.startTime || raceInfo.raceStatus === 'waiting' || raceInfo.raceStatus === 'countdown') {
      return 0;
    }

    // Race is in progress, calculate elapsed time
    return (Date.now() / 1000) - raceInfo.startTime;
  };

  const elapsedTime = calculateElapsedTime();

  const formatTime = (seconds: number): string => {
    // Ensure seconds is a valid number
    if (!isFinite(seconds) || seconds < 0) {
      return '0:00.00';
    }

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

      {/* Off-Track Warning */}
      {car?.is_off_track && !raceInfo.isFinished && (
        <div
          style={{
            marginTop: '15px',
            padding: '10px',
            backgroundColor: 'rgba(244, 67, 54, 0.3)',
            borderRadius: '4px',
            textAlign: 'center',
            fontSize: '14px',
            fontWeight: 'bold',
            color: '#F44336',
            border: '2px solid rgba(244, 67, 54, 0.6)',
            animation: 'pulse 1s infinite'
          }}
        >
          ⚠️ OFF TRACK
        </div>
      )}

      {/* Grace Period Warning */}
      {!raceInfo.isFinished &&
       raceInfo.gracePeriodRemaining !== undefined &&
       raceInfo.gracePeriodRemaining > 0 && (
        <div
          style={{
            marginTop: '15px',
            padding: '10px',
            backgroundColor: 'rgba(255, 165, 0, 0.3)',
            borderRadius: '4px',
            textAlign: 'center',
            fontSize: '14px',
            fontWeight: 'bold',
            color: '#FFA500',
            border: '2px solid rgba(255, 165, 0, 0.6)',
          }}
        >
          ⏱️ GRACE PERIOD: {Math.ceil(raceInfo.gracePeriodRemaining)}s
        </div>
      )}
    </div>
  );
};
