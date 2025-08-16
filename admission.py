import asyncio
import copy
import random
import re
import time

from telethon import Button, TelegramClient, errors, events, tl

RULES = """• Speak English
• Stay on topic (questions about Telethon)
• Be respectful
• Don't ask to ask
• Spam-related uses lead to ban
• Read https://docs.telethon.dev before asking things here"""

CHANNEL = tl.types.PeerChannel(2929947869)

QUIZ_PREFIX = "📚 "

QUIZ_BEGIN = "Begin Quiz"

QUIZ_QUESTIONS = [
    (
        "What questions can you ask?",
        [
            "Questions about Telethon",
            "Questions about any Telegram library",
            "Questions about Telegram",
            "Questions about Python",
        ],
    ),
    (
        "What should you do when someone spams in the group?",
        [
            "/report their message to the admins",
            "Ask them to stop",
            "Tell them off for spamming",
            "Play along and reply to them because it's funny",
        ],
    ),
    (
        "There are things you must do before asking a question. Select the option that does **not** apply.",
        [
            "Ask directly without researching",
            "Read the documentation",
            "Search in the group for my question",
            "Search online for my question",
        ],
    ),
    (
        "Which question from below is okay to ask?",
        [
            '"How can I search for public posts?"',
            '"How can I move 2000 users to my group?"',
            '"Can someone help me? PM me"',
            "Pasting 200 lines of logs without explanation or formatting",
        ],
    ),
    (
        "Can you tag, mention or reply to others to get their attention?",
        [
            "No, only replies when the conversation has already started are OK",
            "Yes, but only to admins",
            "Yes, when my question is very important",
            "Yes, always",
        ],
    ),
]


async def init(bot: TelegramClient):
    USER_STAGES: dict[int, tuple[int, int]] = {}

    def shuffled_quiz(seed):
        state = random.getstate()
        try:
            random.seed(seed)
            quiz = copy.deepcopy(QUIZ_QUESTIONS)
            for _, answers in quiz:
                random.shuffle(answers)
            random.shuffle(quiz)
            return quiz
        finally:
            random.setstate(state)

    async def quiz_check(user, answer):
        stage, started = USER_STAGES.get(user, (None, 0))
        if stage is None:
            return

        if stage == 0:
            if answer != QUIZ_BEGIN:
                await bot.send_message(
                    user,
                    "Please use the custom keyboard to interact with the quiz.",
                    buttons=[
                        [Button.text(f"{QUIZ_PREFIX}{QUIZ_BEGIN}", single_use=True)]
                    ],
                )
                return
        else:
            quiz = shuffled_quiz(seed=started)
            question, _ = quiz[stage - 1]
            correct_answer = next(
                answers[0] for q, answers in QUIZ_QUESTIONS if q == question
            )
            if answer != correct_answer:
                await bot.send_message(
                    user,
                    "Sorry, that was not the correct answer. Please apply to join again to restart the quiz.",
                )
                del USER_STAGES[user]
                await bot(
                    tl.functions.messages.HideChatJoinRequestRequest(
                        peer=CHANNEL, user_id=user, approved=False
                    )
                )
                return

        USER_STAGES[user] = (stage + 1, started)
        await quiz_continue(user)

    async def quiz_continue(user):
        stage, started = USER_STAGES.get(user, (None, 0))
        quiz = shuffled_quiz(seed=started)
        if stage is None:
            await bot.send_message(
                "You need to Apply to join @TelethonChat before starting the quiz."
            )
        elif stage == 0:
            await bot.send_message(
                user,
                f"""Hi! @TelethonChat receives a lot of spam, \
    so you will need to complete a short quiz before joining.

    Don't forget to [read the docs](https://docs.telethon.dev/), \
    and make sure you are using the latest version with `pip3 install -U telethon`. \
    Most problems have already been fixed in newer versions.

    As a reminder, here are the rules of the group:\n{RULES}""",
                buttons=[[Button.text(f"{QUIZ_PREFIX}{QUIZ_BEGIN}", single_use=True)]],
            )
        elif stage <= len(quiz):
            question, answers = quiz[stage - 1]
            await bot.send_message(
                user,
                quiz[stage - 1][0],
                buttons=[
                    [Button.text(f"{QUIZ_PREFIX}{a}", single_use=True)] for a in answers
                ],
            )
        elif stage == len(quiz) + 1:
            try:
                await bot(
                    tl.functions.messages.HideChatJoinRequestRequest(
                        peer=CHANNEL, user_id=user, approved=True
                    )
                )
            except errors.RPCError:
                await bot.send_message(
                    user,
                    "Sorry, something went wrong. Try to re-apply and I will try to accept you again.",
                )
            else:
                await bot.send_message(
                    user,
                    "Nice! You have answered all questions correctly. You can now ask your new question in the group!",
                )
                del USER_STAGES[user]

    @bot.on(events.Raw(tl.types.UpdateBotChatInviteRequester))
    async def handler(e):
        if e.peer != CHANNEL:
            return

        if e.user_id not in USER_STAGES:
            USER_STAGES[e.user_id] = (0, time.time())
        await quiz_continue(e.user_id)

    @bot.on(events.NewMessage(pattern=re.compile(f"^{re.escape(QUIZ_PREFIX)}")))
    async def handler(e):
        user = e.sender_id
        answer = e.raw_text[len(QUIZ_PREFIX) :]
        await quiz_check(user, answer)
