import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import { UserSwitcherProvider } from './components/UserSwitcherProvider'
import { Home, Practice, MultiplayerRace, Editor } from './pages'
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
            <Route path="practice" element={<Practice />} />
            <Route path="multiplayer" element={<MultiplayerRace />} />
            <Route path="race" element={<MultiplayerRace />} />
            <Route path="editor" element={<Editor />} />
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
