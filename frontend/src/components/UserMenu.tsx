/**
 * Header user menu. Logged-out → "Sign in" button. Logged-in → username
 * pill that opens a small dropdown with "Switch user" + "Sign out".
 *
 * Both "Sign in" and "Switch user" go through useUserSwitcher() so the
 * single app-level modal handles the rest of the flow.
 */

import { useEffect, useRef, useState } from 'react';
import { useUsername } from '../hooks/useUsername';
import { useUserSwitcher } from './UserSwitcherProvider';

export const UserMenu: React.FC = () => {
  const { username, loading, clearUsername } = useUsername();
  const { openModal } = useUserSwitcher();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close the dropdown on outside click.
  useEffect(() => {
    if (!dropdownOpen) return;
    const onClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [dropdownOpen]);

  if (loading) {
    return (
      <div
        data-testid="user-menu-loading"
        className="px-3 py-2 rounded bg-white/10 text-sm text-white/70"
      >
        …
      </div>
    );
  }

  if (!username) {
    return (
      <button
        data-testid="user-menu-signin"
        onClick={openModal}
        className="flex items-center gap-2 px-3 py-2 rounded bg-white/10 hover:bg-white/20 transition text-sm font-semibold"
        title="Sign in or create a user"
      >
        <span aria-hidden>👤</span>
        Sign in
      </button>
    );
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        data-testid="user-menu-button"
        onClick={() => setDropdownOpen((o) => !o)}
        className="flex items-center gap-2 px-3 py-2 rounded bg-white/10 hover:bg-white/20 transition text-sm font-semibold"
        aria-expanded={dropdownOpen}
        aria-haspopup="menu"
      >
        <span aria-hidden>👤</span>
        <span data-testid="user-menu-username">{username}</span>
        <span aria-hidden className="text-xs">▾</span>
      </button>

      {dropdownOpen && (
        <div
          data-testid="user-menu-dropdown"
          role="menu"
          className="absolute right-0 mt-2 w-44 bg-gray-800 border border-gray-700 rounded shadow-lg z-50 overflow-hidden"
        >
          <button
            role="menuitem"
            data-testid="user-menu-switch"
            onClick={() => {
              setDropdownOpen(false);
              openModal();
            }}
            className="w-full text-left px-4 py-2 hover:bg-gray-700 text-sm"
          >
            🔄 Switch user
          </button>
          <button
            role="menuitem"
            data-testid="user-menu-signout"
            onClick={() => {
              setDropdownOpen(false);
              clearUsername();
            }}
            className="w-full text-left px-4 py-2 hover:bg-gray-700 text-sm text-red-300"
          >
            ⎋ Sign out
          </button>
        </div>
      )}
    </div>
  );
};

export default UserMenu;
