/**
 * One-time migration utility for moving bot data from localStorage to database.
 *
 * Migrates:
 * - bot_code -> database
 * - bot_name -> database
 *
 * Called automatically when username is first set.
 */

import { createBot } from '../services/botApi';

const OLD_CODE_KEY = 'bot_code';
const OLD_NAME_KEY = 'bot_name';
const MIGRATION_DONE_KEY = 'coderally_migration_done';

export interface MigrationResult {
  migrated: boolean;
  botName?: string;
  error?: string;
}

/**
 * Migrate bot data from localStorage to database.
 *
 * @param username - Username to associate the migrated bot with
 * @returns Migration result indicating success/failure
 */
export async function migrateLocalStorageToDatabase(username: string): Promise<MigrationResult> {
  // Check if migration already done
  const migrationDone = localStorage.getItem(MIGRATION_DONE_KEY);
  if (migrationDone) {
    return { migrated: false };
  }

  // Check if there's anything to migrate
  const oldCode = localStorage.getItem(OLD_CODE_KEY);
  const oldName = localStorage.getItem(OLD_NAME_KEY);

  if (!oldCode && !oldName) {
    // Nothing to migrate, mark as done
    localStorage.setItem(MIGRATION_DONE_KEY, 'true');
    return { migrated: false };
  }

  // Prepare bot data
  const code = oldCode || '# No code found\nclass MyBot:\n    def on_tick(self, state):\n        return {}';
  const name = oldName || 'Migrated Bot';

  try {
    // Create bot in database
    const bot = await createBot(username, { name, code });

    // Clear old keys
    localStorage.removeItem(OLD_CODE_KEY);
    localStorage.removeItem(OLD_NAME_KEY);

    // Mark migration as done
    localStorage.setItem(MIGRATION_DONE_KEY, 'true');

    return {
      migrated: true,
      botName: bot.name,
    };
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : 'Unknown error during migration';
    console.error('Failed to migrate localStorage data:', errorMessage);

    return {
      migrated: false,
      error: errorMessage,
    };
  }
}

/**
 * Reset migration flag (for testing purposes).
 */
export function resetMigrationFlag(): void {
  localStorage.removeItem(MIGRATION_DONE_KEY);
}
