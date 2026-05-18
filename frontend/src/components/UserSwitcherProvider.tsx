/**
 * App-level provider that owns the user-switcher modal.
 *
 * Anywhere in the tree can call `useUserSwitcher().openModal()` to bring
 * up the same modal — header menu, Editor auto-prompt, etc. The modal
 * is rendered once at provider level so there is exactly one instance
 * regardless of how many callers exist.
 */

import { createContext, useCallback, useContext, useState, type ReactNode } from 'react';
import { useUsername } from '../hooks/useUsername';
import { UserSwitcherModal } from './UserSwitcherModal';

interface UserSwitcherContextValue {
  isOpen: boolean;
  openModal: () => void;
  closeModal: () => void;
}

const UserSwitcherContext = createContext<UserSwitcherContextValue | null>(null);

export const UserSwitcherProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [isOpen, setIsOpen] = useState(false);
  const { username, clearUsername } = useUsername();

  const openModal = useCallback(() => setIsOpen(true), []);
  const closeModal = useCallback(() => setIsOpen(false), []);

  return (
    <UserSwitcherContext.Provider value={{ isOpen, openModal, closeModal }}>
      {children}
      <UserSwitcherModal
        isOpen={isOpen}
        onClose={closeModal}
        currentUsername={username}
        onClearUsername={clearUsername}
      />
    </UserSwitcherContext.Provider>
  );
};

export function useUserSwitcher(): UserSwitcherContextValue {
  const ctx = useContext(UserSwitcherContext);
  if (!ctx) {
    throw new Error('useUserSwitcher must be used inside <UserSwitcherProvider>');
  }
  return ctx;
}
