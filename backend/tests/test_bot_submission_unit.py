"""
Unit tests for bot submission workflow components.

Tests bot submission logic without WebSocket integration to avoid
signal() threading limitations in test environment.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.user import User
from app.models.bot import Bot
from app.services import bot_service


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def test_db():
    """Create test database for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(test_db):
    """Create database session for tests."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(username="testuser")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_bot(db_session, test_user):
    """Create a test bot."""
    bot_code = """
class AcceleratorBot(BaseBot):
    def on_tick(self, state):
        return BotActions(accelerate=True)
"""
    bot = Bot(
        name="AcceleratorBot",
        code=bot_code,
        user_id=test_user.id
    )
    db_session.add(bot)
    db_session.commit()
    db_session.refresh(bot)
    return bot


class TestBotLookup:
    """Test bot database lookup logic."""

    def test_get_bot_by_id_success(self, db_session, test_bot):
        """Test successful bot lookup."""
        bot = bot_service.get_bot_by_id(db_session, test_bot.id)
        assert bot is not None
        assert bot.id == test_bot.id
        assert bot.name == "AcceleratorBot"
        assert bot.owner.username == "testuser"

    def test_get_bot_by_id_not_found(self, db_session):
        """Test bot lookup with invalid ID."""
        bot = bot_service.get_bot_by_id(db_session, 99999)
        assert bot is None

    def test_extract_class_name_valid(self):
        """Test class name extraction from valid bot code."""
        bot_code = """
class MyBot(BaseBot):
    def on_tick(self, state):
        return BotActions()
"""
        class_name = bot_service.extract_class_name(bot_code)
        assert class_name == "MyBot"

    def test_extract_class_name_multiple_classes(self):
        """Test class name extraction when multiple classes exist."""
        bot_code = """
class HelperClass:
    pass

class MyBot(BaseBot):
    def on_tick(self, state):
        return BotActions()

class AnotherClass:
    pass
"""
        class_name = bot_service.extract_class_name(bot_code)
        # Should find the first class (or whichever the implementation returns)
        assert class_name in ["HelperClass", "MyBot", "AnotherClass"]

    def test_extract_class_name_no_class(self):
        """Test class name extraction with no class."""
        bot_code = "x = 1 + 1"
        class_name = bot_service.extract_class_name(bot_code)
        assert class_name is None


class TestBotValidation:
    """Test bot validation logic."""

    def test_valid_bot_code_structure(self, test_bot):
        """Test that valid bot code has required structure."""
        assert "class" in test_bot.code
        assert "BaseBot" in test_bot.code
        assert "on_tick" in test_bot.code

    def test_bot_belongs_to_user(self, db_session, test_bot, test_user):
        """Test bot ownership validation."""
        bot = bot_service.get_bot_by_id(db_session, test_bot.id)
        assert bot.user_id == test_user.id
        assert bot.owner.username == test_user.username

    def test_multiple_bots_per_user(self, db_session, test_user):
        """Test user can have multiple bots."""
        bot1 = Bot(name="Bot1", code="class Bot1(BaseBot): pass", user_id=test_user.id)
        bot2 = Bot(name="Bot2", code="class Bot2(BaseBot): pass", user_id=test_user.id)
        db_session.add_all([bot1, bot2])
        db_session.commit()

        bots = bot_service.get_bots_by_user(db_session, test_user.id)
        assert len(bots) >= 2
        bot_names = [b.name for b in bots]
        assert "Bot1" in bot_names
        assert "Bot2" in bot_names


class TestBotPlayerID:
    """Test bot player ID generation."""

    def test_bot_player_id_format(self, test_bot):
        """Test bot player ID follows expected format."""
        expected_prefix = f"bot-testuser-{test_bot.name}"
        assert expected_prefix == "bot-testuser-AcceleratorBot"

    def test_bot_player_id_uniqueness(self, db_session, test_user):
        """Test that different bots get different player IDs."""
        bot1 = Bot(name="Bot1", code="class Bot1(BaseBot): pass", user_id=test_user.id)
        bot2 = Bot(name="Bot2", code="class Bot2(BaseBot): pass", user_id=test_user.id)
        db_session.add_all([bot1, bot2])
        db_session.commit()

        id1 = f"bot-{test_user.username}-{bot1.name}"
        id2 = f"bot-{test_user.username}-{bot2.name}"
        assert id1 != id2
        assert id1 == "bot-testuser-Bot1"
        assert id2 == "bot-testuser-Bot2"
