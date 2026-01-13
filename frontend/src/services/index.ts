// API and WebSocket client exports
export { generateTrack, type GenerateTrackParams } from './trackApi';
export { GameWebSocketClient, type GameWebSocketCallbacks, type GameStateMessage, type ConnectedMessage } from './gameWebSocket';
export {
  getAllUsers,
  registerUser,
  getUser,
  deleteUser,
  getUserBots,
  getBot,
  createBot,
  updateBot,
  deleteBot,
  type User,
  type Bot,
  type BotListItem,
  type CreateBotRequest,
  type UpdateBotRequest,
} from './botApi';
export {
  fetchLobbies,
  fetchLobby,
  createLobby,
  updateLobbySettings,
  disbandLobby,
  type LobbySettings,
  type LobbyMember,
  type LobbyListItem,
  type Lobby,
  type CreateLobbyRequest,
  type UpdateSettingsRequest,
} from './lobbyApi';
