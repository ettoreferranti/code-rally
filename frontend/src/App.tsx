import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import { Home, Practice, MultiplayerRace, Editor } from './pages'
import LobbyBrowser from './pages/LobbyBrowser'
import LobbyWaitingRoom from './pages/LobbyWaitingRoom'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="practice" element={<Practice />} />
          <Route path="multiplayer" element={<MultiplayerRace />} />
          <Route path="race" element={<MultiplayerRace />} />
          <Route path="editor" element={<Editor />} />
          <Route path="lobbies" element={<LobbyBrowser />} />
          <Route path="lobby/:lobbyId" element={<LobbyWaitingRoom />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
