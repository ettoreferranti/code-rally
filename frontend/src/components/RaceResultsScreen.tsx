/**
 * Race Results Screen - displays final race results with positions, times, and points.
 */

import React from 'react';
import type { PlayerResult } from '../game/types';

interface RaceResultsScreenProps {
  results: PlayerResult[];
  currentPlayerId: string;
  onClose: () => void;
}

export const RaceResultsScreen: React.FC<RaceResultsScreenProps> = ({
  results,
  currentPlayerId,
  onClose
}) => {
  const formatTime = (seconds: number | null): string => {
    if (seconds === null) {
      return 'DNF';
    }

    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 100);
    return `${mins}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
  };

  const formatPosition = (position: number | null, dnf: boolean): string => {
    if (dnf || position === null) {
      return 'DNF';
    }

    const suffixes = ['th', 'st', 'nd', 'rd'];
    const value = position % 100;
    const suffix = suffixes[(value - 20) % 10] || suffixes[value] || suffixes[0];
    return `${position}${suffix}`;
  };

  // Sort results: finished players by position, then DNF players
  const sortedResults = [...results].sort((a, b) => {
    if (a.dnf && !b.dnf) return 1;
    if (!a.dnf && b.dnf) return -1;
    if (a.dnf && b.dnf) return 0;
    if (a.position === null && b.position !== null) return 1;
    if (a.position !== null && b.position === null) return -1;
    return (a.position || 0) - (b.position || 0);
  });

  const currentPlayerResult = results.find(r => r.playerId === currentPlayerId);

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(0, 0, 0, 0.85)',
        zIndex: 100,
      }}
    >
      <div
        style={{
          backgroundColor: '#1f2937',
          borderRadius: '12px',
          padding: '32px',
          maxWidth: '600px',
          width: '90%',
          color: 'white',
          fontFamily: 'monospace',
        }}
      >
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <h2 style={{ fontSize: '36px', fontWeight: 'bold', marginBottom: '8px', color: '#4CAF50' }}>
            RACE COMPLETE!
          </h2>
          {currentPlayerResult && (
            <div style={{ fontSize: '24px', marginTop: '16px' }}>
              You finished{' '}
              <span style={{
                fontWeight: 'bold',
                color: currentPlayerResult.dnf ? '#F44336' : '#4CAF50'
              }}>
                {formatPosition(currentPlayerResult.position, currentPlayerResult.dnf)}
              </span>
              {!currentPlayerResult.dnf && (
                <>
                  {' '}with{' '}
                  <span style={{ fontWeight: 'bold', color: '#FFD700' }}>
                    {currentPlayerResult.points} points
                  </span>
                </>
              )}
            </div>
          )}
        </div>

        {/* Results Table */}
        <div style={{ marginBottom: '24px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #4b5563' }}>
                <th style={{ padding: '12px 8px', textAlign: 'left', color: '#9ca3af' }}>Position</th>
                <th style={{ padding: '12px 8px', textAlign: 'left', color: '#9ca3af' }}>Player</th>
                <th style={{ padding: '12px 8px', textAlign: 'right', color: '#9ca3af' }}>Time</th>
                <th style={{ padding: '12px 8px', textAlign: 'right', color: '#9ca3af' }}>Points</th>
              </tr>
            </thead>
            <tbody>
              {sortedResults.map((result) => {
                const isCurrentPlayer = result.playerId === currentPlayerId;
                return (
                  <tr
                    key={result.playerId}
                    style={{
                      backgroundColor: isCurrentPlayer ? 'rgba(76, 175, 80, 0.2)' : 'transparent',
                      borderBottom: '1px solid #374151',
                    }}
                  >
                    <td
                      style={{
                        padding: '12px 8px',
                        fontWeight: isCurrentPlayer ? 'bold' : 'normal',
                        color: result.dnf ? '#F44336' : 'white',
                      }}
                    >
                      {formatPosition(result.position, result.dnf)}
                    </td>
                    <td
                      style={{
                        padding: '12px 8px',
                        fontWeight: isCurrentPlayer ? 'bold' : 'normal',
                      }}
                    >
                      {isCurrentPlayer ? 'You' : result.playerName || result.playerId.substring(0, 8)}
                      {isCurrentPlayer && ' ★'}
                    </td>
                    <td
                      style={{
                        padding: '12px 8px',
                        textAlign: 'right',
                        color: result.dnf ? '#F44336' : '#9ca3af',
                      }}
                    >
                      {formatTime(result.finishTime)}
                    </td>
                    <td
                      style={{
                        padding: '12px 8px',
                        textAlign: 'right',
                        fontWeight: result.points > 0 ? 'bold' : 'normal',
                        color: result.points > 0 ? '#FFD700' : '#9ca3af',
                      }}
                    >
                      {result.points}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Footer with DNF explanation if any DNFs */}
        {sortedResults.some(r => r.dnf) && (
          <div
            style={{
              marginBottom: '24px',
              padding: '12px',
              backgroundColor: 'rgba(244, 67, 54, 0.2)',
              borderRadius: '6px',
              fontSize: '14px',
              color: '#F44336',
              textAlign: 'center',
            }}
          >
            DNF = Did Not Finish (failed to complete within grace period)
          </div>
        )}

        {/* Close Button */}
        <div style={{ textAlign: 'center' }}>
          <button
            onClick={onClose}
            style={{
              padding: '12px 32px',
              backgroundColor: '#4CAF50',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              fontSize: '16px',
              fontWeight: 'bold',
              cursor: 'pointer',
              transition: 'background-color 0.2s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#45a049';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = '#4CAF50';
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
