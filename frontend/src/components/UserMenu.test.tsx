/**
 * UserMenu tests. The provider hookup is mocked so we can drive the menu
 * deterministically without touching localStorage or the backend.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

const openModal = vi.fn();
const clearUsername = vi.fn();
let currentUsername: string | null = 'alice';
let currentLoading = false;

vi.mock('../hooks/useUsername', () => ({
  useUsername: () => ({
    username: currentUsername,
    loading: currentLoading,
    clearUsername,
  }),
}));

vi.mock('./UserSwitcherProvider', () => ({
  useUserSwitcher: () => ({ isOpen: false, openModal, closeModal: vi.fn() }),
}));

import { UserMenu } from './UserMenu';

describe('UserMenu', () => {
  beforeEach(() => {
    openModal.mockClear();
    clearUsername.mockClear();
    currentUsername = 'alice';
    currentLoading = false;
  });

  it('renders a loading pill while the username hook is loading', () => {
    currentLoading = true;
    render(<UserMenu />);
    expect(screen.getByTestId('user-menu-loading')).toBeInTheDocument();
  });

  it('shows the Sign in button when there is no user', async () => {
    currentUsername = null;
    render(<UserMenu />);

    const button = screen.getByTestId('user-menu-signin');
    expect(button).toHaveTextContent(/Sign in/);

    await userEvent.click(button);
    expect(openModal).toHaveBeenCalledTimes(1);
  });

  it('shows the username when logged in and opens the dropdown on click', async () => {
    render(<UserMenu />);

    expect(screen.getByTestId('user-menu-username')).toHaveTextContent('alice');
    expect(screen.queryByTestId('user-menu-dropdown')).toBeNull();

    await userEvent.click(screen.getByTestId('user-menu-button'));
    expect(screen.getByTestId('user-menu-dropdown')).toBeInTheDocument();
  });

  it('routes "Switch user" through the provider modal', async () => {
    render(<UserMenu />);
    await userEvent.click(screen.getByTestId('user-menu-button'));
    await userEvent.click(screen.getByTestId('user-menu-switch'));

    expect(openModal).toHaveBeenCalledTimes(1);
    // Dropdown closes after the action.
    expect(screen.queryByTestId('user-menu-dropdown')).toBeNull();
  });

  it('calls clearUsername on Sign out', async () => {
    render(<UserMenu />);
    await userEvent.click(screen.getByTestId('user-menu-button'));
    await userEvent.click(screen.getByTestId('user-menu-signout'));

    expect(clearUsername).toHaveBeenCalledTimes(1);
    expect(openModal).not.toHaveBeenCalled();
  });

  it('closes the dropdown when clicking outside', async () => {
    render(
      <div>
        <UserMenu />
        <button data-testid="outside">outside</button>
      </div>,
    );
    await userEvent.click(screen.getByTestId('user-menu-button'));
    expect(screen.getByTestId('user-menu-dropdown')).toBeInTheDocument();

    await userEvent.click(screen.getByTestId('outside'));
    expect(screen.queryByTestId('user-menu-dropdown')).toBeNull();
  });
});
