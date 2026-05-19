import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import { UserSwitcherProvider } from './components/UserSwitcherProvider'
import { Home, MultiplayerRace, Tinker } from './pages'
import LobbyBrowser from './pages/LobbyBrowser'
import LobbyWaitingRoom from './pages/LobbyWaitingRoom'
import JoinLobby from './pages/JoinLobby'

function App() {
  return (
    <BrowserRouter>
      <UserSwitcherProvider>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Home />} />
            <Route path="race" element={<MultiplayerRace />} />
            <Route path="tinker" element={<Tinker />} />
            {/* Old /editor URL redirects to the new Tinker page. */}
            <Route path="editor" element={<Navigate to="/tinker" replace />} />
            <Route path="lobbies" element={<LobbyBrowser />} />
            <Route path="lobby/:lobbyId" element={<LobbyWaitingRoom />} />
            <Route path="join/:code" element={<JoinLobby />} />
          </Route>
        </Routes>
      </UserSwitcherProvider>
    </BrowserRouter>
  )
}

export default App
