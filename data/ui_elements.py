"""UI Element Dictionary — visual cheat sheet for vibe coders.

20 common UI elements with ASCII wireframes, descriptions, and AI prompts.
Element NAMES stay English (AI needs English terms), descriptions have EN + UA.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UIElement:
    name: str           # English name (what to tell AI)
    aliases: list[str]  # alternative names
    category: str       # "layout", "interactive", "content", "form"
    wireframe: str      # ASCII art
    desc_en: str        # one-line description
    desc_ua: str
    prompt_en: str      # example prompt to AI
    prompt_ua: str


UI_ELEMENTS: list[UIElement] = [
    # === LAYOUT ===
    UIElement(
        name="Navbar / Navigation Bar",
        aliases=["nav", "top menu", "header menu"],
        category="layout",
        wireframe=(
            "+--------------------------------------------------+\n"
            "| Logo   Home  About  Contact         [Login]      |\n"
            "+--------------------------------------------------+"
        ),
        desc_en="The bar at the very top. Usually has links + logo.",
        desc_ua="Панель зверху сторінки. Зазвичай має посилання + логотип.",
        prompt_en="change the navbar links / add a button to the navigation bar on the right side",
        prompt_ua="зміни посилання в навбарі / додай кнопку праворуч у панелі навігації",
    ),
    UIElement(
        name="Sidebar",
        aliases=["side menu", "left menu", "nav panel"],
        category="layout",
        wireframe=(
            "+------+-------------------------------------------+\n"
            "| Home |                                            |\n"
            "| Dash |  (main content here)                       |\n"
            "| Users|                                            |\n"
            "| Logs |                                            |\n"
            "+------+-------------------------------------------+"
        ),
        desc_en="Vertical menu on the left (sometimes right).",
        desc_ua="Вертикальне меню зліва (іноді справа).",
        prompt_en="add a new item to the sidebar / move Settings to the bottom of the sidebar",
        prompt_ua="додай новий пункт у сайдбар / перемісти Налаштування вниз сайдбару",
    ),
    UIElement(
        name="Footer",
        aliases=["bottom bar", "page footer"],
        category="layout",
        wireframe=(
            "+--------------------------------------------------+\n"
            "|                  (page content)                   |\n"
            "+--------------------------------------------------+\n"
            "| (c) 2026 MyApp  |  Terms  |  Privacy  |  Contact |\n"
            "+--------------------------------------------------+"
        ),
        desc_en="The bar at the very bottom. Links, copyright, contacts.",
        desc_ua="Панель внизу сторінки. Посилання, копірайт, контакти.",
        prompt_en="add social media links to the footer",
        prompt_ua="додай посилання на соцмережі у футер",
    ),
    UIElement(
        name="Header / Hero",
        aliases=["hero section", "banner", "jumbotron"],
        category="layout",
        wireframe=(
            "+--------------------------------------------------+\n"
            "|                                                    |\n"
            "|        Welcome to Our App                         |\n"
            "|        The best thing since sliced bread          |\n"
            "|              [ Get Started ]                      |\n"
            "|                                                    |\n"
            "+--------------------------------------------------+"
        ),
        desc_en="Big section at the top with title, subtitle, and a call-to-action button.",
        desc_ua="Великий блок зверху з заголовком, підзаголовком і кнопкою дії.",
        prompt_en="change the hero section text / make the hero background darker",
        prompt_ua="зміни текст у hero-секції / зроби фон hero темнішим",
    ),
    UIElement(
        name="Breadcrumb",
        aliases=["breadcrumbs", "path trail"],
        category="layout",
        wireframe=(
            "  Home > Products > Shoes > Nike Air Max"
        ),
        desc_en="Shows where you are: a trail of links from home to current page.",
        desc_ua="Показує де ти: ланцюжок посилань від головної до поточної сторінки.",
        prompt_en="add breadcrumbs above the page title",
        prompt_ua="додай хлібні крихти над заголовком сторінки",
    ),
    UIElement(
        name="Tab / Tab Bar",
        aliases=["tabs", "tab navigation"],
        category="layout",
        wireframe=(
            "+--------+--------+--------+\n"
            "| Tab 1  | TAB 2  | Tab 3  |\n"
            "+--------+========+--------+\n"
            "|                           |\n"
            "|  Content of Tab 2         |\n"
            "|                           |\n"
            "+---------------------------+"
        ),
        desc_en="Horizontal buttons that switch content below. Active tab is highlighted.",
        desc_ua="Горизонтальні кнопки, що перемикають контент нижче. Активний таб підсвічений.",
        prompt_en="add a new tab called 'Settings' / change the active tab style",
        prompt_ua="додай новий таб 'Налаштування' / зміни стиль активного табу",
    ),

    # === INTERACTIVE ===
    UIElement(
        name="Modal / Dialog / Popup",
        aliases=["lightbox", "overlay", "confirmation dialog"],
        category="interactive",
        wireframe=(
            "+--------------------------------------------------+\n"
            "|          +- Delete Item? ------+                  |\n"
            "|          | Are you sure?       |                  |\n"
            "|          |   [Yes]   [No]      |                  |\n"
            "|          +---------------------+                  |\n"
            "+--------------------------------------------------+"
        ),
        desc_en="A box that appears on top of everything. Blocks the page behind it.",
        desc_ua="Вікно, яке з'являється поверх всього. Блокує сторінку за собою.",
        prompt_en="show a confirmation modal before delete / add a popup that asks for user input",
        prompt_ua="покажи модалку підтвердження перед видаленням / додай попап з введенням",
    ),
    UIElement(
        name="Dropdown / Select",
        aliases=["combo box", "select menu", "picker"],
        category="interactive",
        wireframe=(
            "  Country: [ United States    v ]\n"
            "           +--------------------+\n"
            "           | United States      |\n"
            "           | Canada             |\n"
            "           | United Kingdom     |\n"
            "           +--------------------+"
        ),
        desc_en="Click to open a list of options. Pick one.",
        desc_ua="Натискаєш — відкривається список. Обираєш один варіант.",
        prompt_en="change the dropdown options / make the select searchable",
        prompt_ua="зміни варіанти у дропдауні / зроби селект з пошуком",
    ),
    UIElement(
        name="Toast / Notification",
        aliases=["snackbar", "flash message", "alert banner"],
        category="interactive",
        wireframe=(
            "                    +- Saved! --------+\n"
            "                    | Changes saved    |\n"
            "                    | successfully.    |\n"
            "                    +-----------------+"
        ),
        desc_en="Small message that appears briefly and disappears. Usually at the top or bottom.",
        desc_ua="Маленьке повідомлення, що з'являється ненадовго і зникає.",
        prompt_en="show a success toast after saving / add error notification on failure",
        prompt_ua="покажи toast 'збережено' після збереження / додай нотифікацію про помилку",
    ),
    UIElement(
        name="Tooltip",
        aliases=["hover text", "hint", "popover"],
        category="interactive",
        wireframe=(
            "           +- This deletes ----+\n"
            "           | everything. Are   |\n"
            "           | you sure?         |\n"
            "           +-------v-----------+\n"
            "                [Delete]"
        ),
        desc_en="Text that appears when you hover over something. Explains what the thing does.",
        desc_ua="Текст, що з'являється при наведенні курсора. Пояснює що це робить.",
        prompt_en="add a tooltip to the delete button explaining what it does",
        prompt_ua="додай тултіп до кнопки видалення з поясненням",
    ),
    UIElement(
        name="Accordion / Collapsible",
        aliases=["expandable", "collapse", "FAQ section"],
        category="interactive",
        wireframe=(
            "+ What is your return policy?    [-]\n"
            "|  You can return items within      |\n"
            "|  30 days of purchase.             |\n"
            "+-----------------------------------+\n"
            "+ How do I track my order?       [+]\n"
            "+-----------------------------------+\n"
            "+ Do you ship internationally?   [+]\n"
            "+-----------------------------------+"
        ),
        desc_en="Sections that expand/collapse when clicked. Only one open at a time.",
        desc_ua="Секції, що розгортаються/згортаються при кліку.",
        prompt_en="add an FAQ accordion section / make all accordion items collapsed by default",
        prompt_ua="додай секцію FAQ з акордеоном / зроби все згорнутим за замовчуванням",
    ),
    UIElement(
        name="Toggle / Switch",
        aliases=["on/off switch", "boolean toggle"],
        category="interactive",
        wireframe=(
            "  Dark mode:   [====O ]  OFF\n"
            "  Notifications:  [ O====]  ON"
        ),
        desc_en="Slide switch. On or off. Like a light switch.",
        desc_ua="Перемикач. Увімкнено або вимкнено. Як вимикач світла.",
        prompt_en="add a dark mode toggle in settings / change toggle to a checkbox",
        prompt_ua="додай перемикач темної теми в налаштуваннях / заміни тогл на чекбокс",
    ),

    # === CONTENT ===
    UIElement(
        name="Card",
        aliases=["content card", "info card", "tile"],
        category="content",
        wireframe=(
            "+--------------------+\n"
            "|  [  image  ]       |\n"
            "|                    |\n"
            "|  Product Name      |\n"
            "|  $29.99            |\n"
            "|  [ Add to Cart ]   |\n"
            "+--------------------+"
        ),
        desc_en="Box with image + text + button. Used for products, articles, users.",
        desc_ua="Картка з картинкою + текст + кнопка. Для товарів, статей, юзерів.",
        prompt_en="add a card grid for products / change card layout to horizontal",
        prompt_ua="додай сітку карток для товарів / зроби картку горизонтальною",
    ),
    UIElement(
        name="Table",
        aliases=["data table", "grid", "data grid"],
        category="content",
        wireframe=(
            "+------+----------+--------+--------+\n"
            "| ID   | Name     | Email  | Role   |\n"
            "+------+----------+--------+--------+\n"
            "| 1    | Alice    | a@b.c  | Admin  |\n"
            "| 2    | Bob      | b@b.c  | User   |\n"
            "+------+----------+--------+--------+"
        ),
        desc_en="Rows and columns of data. Can sort, filter, paginate.",
        desc_ua="Рядки і стовпці з даними. Можна сортувати, фільтрувати, пагінувати.",
        prompt_en="add sorting to the table columns / make the table rows clickable",
        prompt_ua="додай сортування по стовпцях / зроби рядки таблиці клікабельними",
    ),
    UIElement(
        name="Badge / Tag / Chip",
        aliases=["label", "pill", "status badge"],
        category="content",
        wireframe=(
            "  John Smith  [Admin]  [Active]\n"
            "\n"
            "  Tags: [React] [TypeScript] [Docker] [x]"
        ),
        desc_en="Small colored label. Shows status, category, or tag.",
        desc_ua="Маленька кольорова мітка. Показує статус, категорію або тег.",
        prompt_en="add a status badge next to usernames / make tags removable with X button",
        prompt_ua="додай бейдж статусу біля імен / зроби теги з кнопкою видалення",
    ),
    UIElement(
        name="Avatar",
        aliases=["user photo", "profile picture", "user icon"],
        category="content",
        wireframe=(
            "  +---+\n"
            "  |:) |  John Smith\n"
            "  +---+  Admin"
        ),
        desc_en="User photo circle. Usually with name next to it.",
        desc_ua="Кругле фото юзера. Зазвичай з іменем поруч.",
        prompt_en="show user avatar in the navbar / add initials fallback when no photo",
        prompt_ua="покажи аватар юзера в навбарі / покажи ініціали коли немає фото",
    ),
    UIElement(
        name="Pagination",
        aliases=["page numbers", "pager"],
        category="content",
        wireframe=(
            "  < 1  2  [3]  4  5 ... 10 >"
        ),
        desc_en="Page numbers at the bottom. Navigate through long lists.",
        desc_ua="Номери сторінок внизу. Для навігації по довгих списках.",
        prompt_en="add pagination to the user list / change to infinite scroll instead",
        prompt_ua="додай пагінацію до списку юзерів / заміни на нескінченний скрол",
    ),
    UIElement(
        name="List / List Item",
        aliases=["ordered list", "unordered list", "menu list"],
        category="content",
        wireframe=(
            "  * Buy groceries\n"
            "  * Walk the dog\n"
            "  * Fix that bug\n"
            "  * Deploy to production"
        ),
        desc_en="Vertical list of items. Can be plain text, links, or complex rows.",
        desc_ua="Вертикальний список елементів. Може бути текст, посилання або складні рядки.",
        prompt_en="add a task list with checkboxes / make list items draggable",
        prompt_ua="додай список задач з чекбоксами / зроби елементи списку перетягуваними",
    ),

    # === FORM ===
    UIElement(
        name="Input / Text Field",
        aliases=["text input", "text box", "form field"],
        category="form",
        wireframe=(
            "  Email: [  user@example.com        ]\n"
            "  Password: [ ********               ]"
        ),
        desc_en="A box where user types text. Can have placeholder, label, validation.",
        desc_ua="Поле, куди юзер вводить текст. Може мати плейсхолдер, мітку, валідацію.",
        prompt_en="add email validation to the input / show error message below the field",
        prompt_ua="додай валідацію email / покажи помилку під полем введення",
    ),
    UIElement(
        name="Textarea",
        aliases=["text area", "multiline input", "comment box"],
        category="form",
        wireframe=(
            "  Message:\n"
            "  +------------------------------+\n"
            "  | Type your message here...    |\n"
            "  |                              |\n"
            "  |                              |\n"
            "  +------------------------------+"
        ),
        desc_en="Multi-line text input. For comments, descriptions, messages.",
        desc_ua="Багаторядкове поле вводу. Для коментарів, описів, повідомлень.",
        prompt_en="add a character counter to the textarea / make textarea auto-resize",
        prompt_ua="додай лічильник символів / зроби textarea з автозміною висоти",
    ),
    UIElement(
        name="Checkbox / Radio",
        aliases=["check box", "radio button", "option"],
        category="form",
        wireframe=(
            "  [x] I agree to terms\n"
            "  [ ] Subscribe to newsletter\n"
            "\n"
            "  ( ) Small  (*) Medium  ( ) Large"
        ),
        desc_en="Checkbox = pick many. Radio = pick one. Square vs circle.",
        desc_ua="Чекбокс = обрати кілька. Радіо = обрати одне. Квадрат vs коло.",
        prompt_en="add a 'select all' checkbox / change radio buttons to a dropdown",
        prompt_ua="додай чекбокс 'обрати все' / заміни радіо-кнопки на дропдаун",
    ),
    UIElement(
        name="Button",
        aliases=["action button", "submit button", "CTA"],
        category="form",
        wireframe=(
            "  [ Save ]  [ Cancel ]  [ Delete ]\n"
            "\n"
            "  Types: primary (blue), secondary (gray),\n"
            "         danger (red), ghost (text only)"
        ),
        desc_en="Clickable action. Has types: primary, secondary, danger, ghost.",
        desc_ua="Клікабельна дія. Є типи: primary, secondary, danger, ghost.",
        prompt_en="change the submit button to primary style / add a loading spinner to the button",
        prompt_ua="зміни кнопку на primary стиль / додай спінер завантаження на кнопку",
    ),
]


def get_elements_by_category() -> dict[str, list[UIElement]]:
    """Group elements by category."""
    result: dict[str, list[UIElement]] = {}
    for el in UI_ELEMENTS:
        result.setdefault(el.category, []).append(el)
    return result


def get_element_names() -> list[str]:
    """Return list of all element names (for detection in code)."""
    return [el.name for el in UI_ELEMENTS]
