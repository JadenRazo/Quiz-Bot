from services.database import ConfigError, DatabaseService
from services.database_operations.quiz_stats_ops import record_batch_quiz_results


def test_database_package_exports_runtime_service():
    assert DatabaseService.__module__ == "services.database_service"
    assert ConfigError.__module__ == "services.database_service"


async def test_batch_results_do_not_require_a_discord_context():
    class FakeDatabaseService:
        def __init__(self):
            self.sessions = []

        async def record_user_quiz_session(
            self,
            user_id,
            username,
            quiz_id,
            topic,
            correct,
            wrong,
            points,
            difficulty,
            category,
            guild_id=None,
        ):
            self.sessions.append(
                {
                    "user_id": user_id,
                    "username": username,
                    "quiz_id": quiz_id,
                    "topic": topic,
                    "correct": correct,
                    "wrong": wrong,
                    "points": points,
                    "difficulty": difficulty,
                    "category": category,
                    "guild_id": guild_id,
                }
            )
            return True

        async def batch_update_user_stats(self, results):
            return bool(results)

        async def batch_increment_quizzes_taken(self, results):
            return bool(results)

    database = FakeDatabaseService()
    success = await record_batch_quiz_results(
        db_service=database,
        quiz_id="quiz-1",
        topic="science",
        results=[
            {
                "user_id": 123,
                "username": "UnknownUser",
                "correct": 4,
                "wrong": 1,
                "points": 40,
                "difficulty": "medium",
                "category": "science",
            }
        ],
        guild_id=456,
    )

    assert success is True
    assert database.sessions == [
        {
            "user_id": 123,
            "username": "UnknownUser",
            "quiz_id": "quiz-1",
            "topic": "science",
            "correct": 4,
            "wrong": 1,
            "points": 40,
            "difficulty": "medium",
            "category": "science",
            "guild_id": 456,
        }
    ]
