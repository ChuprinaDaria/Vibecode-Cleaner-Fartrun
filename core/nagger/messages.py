import random
from i18n import get_language

MESSAGES: dict[str, dict[int, list[str]]] = {
    "en": {
        1: [
            "You burned {tokens} tokens. Could've read a book instead.",
            "Claude is working. Are you? Just sitting watching AI code for you.",
            "You know what's free? Fresh air outside. Go breathe some.",
            "{tokens} tokens. That many neurons die while you sit here.",
            "IDE open for {sessions} sessions straight. Monitor sees you more than the sun.",
            "Maybe go outside? There's grass. Green. Real. Not CSS.",
            "Asking AI instead of Stack Overflow. Progress or degradation?",
            "Claude won't judge, but I will. Stand up. Stretch.",
            "Tokens spent: {tokens}. Calories burned: 0. Priorities?",
            "Every token is your spine screaming 'get out of the chair!'",
            "Even the cursor blinks \u2014 hinting you should blink too.",
            "Dishes in the sink are judging you.",
        ],
        2: [
            "{tokens} tokens! Writing a novel through Claude?",
            "At this rate you'll burn out before the tokens run out.",
            "Ever looked for a girlfriend? No? She'd drag you from the monitor.",
            "Your chair is praying. {tokens} tokens and zero breaks.",
            "You spend tokens like an oligarch \u2014 senselessly and plenty.",
            "Even Anthropic's servers suspect you're a bot.",
            "Maybe find a girlfriend? Or at least a cat? Something alive besides your IDE.",
            "Your monitor sees you more than your friends. If you have any.",
            "A GPU in some data center suffers for your 'try again'.",
            "{tokens} tokens. You could've learned to do this yourself by now.",
            "Even vim users exit sometimes. At least accidentally.",
            "Tokens aren't free. Neither is your youth. Both slipping away.",
        ],
        3: [
            "{tokens} TOKENS?! Seriously? Sell the laptop, buy a gym membership.",
            "Anthropic added you to 'VIP clients'. In a bad way.",
            "At {tokens} tokens \u2014 you're not a dev, you're an addict.",
            "Some people touch grass. You touch keyboards. There's a difference.",
            "Girlfriend? Partner? Friend? A houseplant? No? Then at least close the IDE.",
            "You've been here so long vitamin D is a legend.",
            "For these tokens you could've hired a junior. A living one. With legs.",
            "Even dark mode won't hide how long you've been here.",
            "You asked Claude {tokens} tokens. Claude asks: are you okay?",
            "CTRL+C for the session. CTRL+Z for your life. Both overdue.",
            "Even CI/CD pipelines have cooldowns. You don't.",
            "You're like a cron job without a sleep interval. Stop.",
        ],
        4: [
            "{tokens} TOKENS! This isn't work. It's addiction. Admit it.",
            "WARNING: At this rate you'll become a prompt, not a person.",
            "Even Elon Musk sleeps sometimes. Do you?",
            "Over half a million tokens. Your spine hates you. So do I.",
            "You're no longer a developer. You're an interface between a chair and Claude.",
            "SYSTEM ALERT: Carbon-based prompt wrapper detected. Needs reboot (sleep).",
            "If every token were a step \u2014 you'd have walked to the gym by now.",
            "You spent more on tokens than food this month. Fact.",
            "FINAL WARNING: Next message will be from your orthopedist.",
            "GG. {tokens} tokens. Stand up. Go out. Touch grass. Find a girlfriend. In that order.",
            "Even Bitcoin miners take cooling breaks. You don't.",
            "You're like while(true) without break. That's not a feature, it's a bug.",
        ],
    },
    "ua": {
        1: [
            "Ти вже спалив {tokens} токенів. Книжку б прочитав за цей час.",
            "Claude працює. А ти? Сидиш і дивишся як AI пише за тебе.",
            "Знаєш що безкоштовне? Повітря на вулиці. Сходи подихай.",
            "{tokens} токенів. Стільки ж нейронів помирає поки ти тут сидиш.",
            "IDE відкрита {sessions} сесій поспіль. Монітор бачить тебе частіше ніж сонце.",
            "Може вийдеш на вулицю? Там є трава. Зелена. Справжня. Не CSS.",
            "Ти питаєш AI замість Stack Overflow. Прогрес чи деградація?",
            "Claude не засудить, але я \u2014 так. Встань. Розімнись.",
            "Токенів витрачено: {tokens}. Калорій спалено: 0. Пріоритети?",
            "Кожен токен \u2014 це крик твоєї спини 'встань з крісла!'",
            "Посуд в раковині дивиться на тебе з осудом.",
            "{sessions} сесій сьогодні. Це більше ніж твоїх прогулянок за тиждень.",
        ],
        2: [
            "{tokens} токенів! Ти що, роман пишеш через Claude?",
            "При такому темпі ти вигориш раніше ніж скінчаться токени.",
            "Жінку шукав? Ні? А вона б тебе від монітора відтягнула.",
            "Стілець під тобою вже молиться. {tokens} токенів і жодної перерви.",
            "Ти витрачаєш токени як олігарх \u2014 без сенсу і багато.",
            "Навіть сервери Anthropic вже підозрюють що ти бот.",
            "Може знайдеш дівчину? Або хоча б кота? Щось живе крім IDE.",
            "Монітор тебе бачить частіше ніж твої друзі. Якщо вони є.",
            "GPU десь в дата-центрі страждає заради твого 'а спробуй ще раз'.",
            "{tokens} токенів. Ти міг би вже навчитись робити це сам.",
            "Навіть vim users іноді виходять. Хоча б випадково.",
            "Токени не безкоштовні. Як і твоя молодість. Обидва спливають.",
        ],
        3: [
            "{tokens} ТОКЕНІВ?! Ти серйозно? Продай ноут, купи абонемент в зал.",
            "Anthropic тебе вже внесли в 'VIP клієнтів'. В поганому сенсі.",
            "При {tokens} токенах \u2014 ти не програміст, ти залежний.",
            "Знаєш, є люди які трогають траву. Ти \u2014 трогаєш клавіатуру. Різниця є.",
            "Жінка? Дівчина? Подруга? Хоч фікус? Ні? Тоді хоч закрий IDE.",
            "Ти сидиш тут так довго, що вітамін D вже легенда.",
            "За ці токени можна було найняти джуна. Живого. З ногами, щоб ходив.",
            "Навіть dark mode не приховає те, скільки ти тут сидиш.",
            "Ти запитав Claude {tokens} токенів. Claude запитує: ти добре?",
            "CTRL+C для сесії. CTRL+Z для свого життя. Обидва давно пора.",
            "Навіть CI/CD pipeline має cooldown. А ти \u2014 ні.",
            "Ти як cron job без sleep interval. Зупинись.",
        ],
        4: [
            "{tokens} ТОКЕНІВ! Це не робота. Це залежність. Визнай це.",
            "УВАГА: При такому темпі ти скоро станеш prompt, а не людиною.",
            "Навіть Ілон Маск іноді спить. А ти?",
            "Більше півмільйона токенів. Твоя спина ненавидить тебе. І я теж.",
            "Ти вже не розробник. Ти \u2014 інтерфейс між стільцем і Claude.",
            "SYSTEM ALERT: Виявлено carbon-based prompt wrapper. Потребує перезавантаження (сон).",
            "Якщо б кожен токен був кроком \u2014 ти б вже дійшов до спортзалу.",
            "Ти витратив більше на токени ніж на їжу цього місяця. Факт.",
            "ФІНАЛЬНЕ ПОПЕРЕДЖЕННЯ: Наступне повідомлення буде від твого ортопеда.",
            "GG. {tokens} токенів. Встань. Вийди. Торкни траву. Знайди дівчину. В такому порядку.",
            "Навіть Bitcoin miners роблять перерви на охолодження. Ти \u2014 ні.",
            "Ти як while(true) без break. Це не фіча, це баг.",
        ],
    },
}


def _fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def get_nag_message(level: int, tokens: int = 0, sessions: int = 0) -> str:
    lang = get_language()
    level = max(1, min(4, level))
    pool = MESSAGES.get(lang, MESSAGES["en"]).get(level, MESSAGES["en"][1])
    msg = random.choice(pool)
    return msg.format(tokens=_fmt_tokens(tokens), sessions=sessions)


def get_nag_level(billable: int) -> int:
    if billable <= 50_000:
        return 1
    if billable <= 150_000:
        return 2
    if billable <= 500_000:
        return 3
    return 4
