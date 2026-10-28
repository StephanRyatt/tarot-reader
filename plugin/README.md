# Tarot Reader

Tarot readings from real draws. The plugin pairs a remote MCP server, which shuffles a full 78-card Rider-Waite deck
and deals one card per spread position, with a counseling skill that reads those cards and only those cards.

## Use it

Ask for a reading in your own words, for example "Do a three-card reading about my week" or "Should I take the new
job or stay?". The skill asks Claude to design a spread for your question, draw it once, and open with which way the cards lean,
naming the cards behind each claim. The decision stays with you.

Named spreads are built in: Card of the Day, Daily Alignment, Daily Focus, Weekly Path, Weekly Evolution, Past,
Present, Future, Decision and Celtic Cross. In claude.ai and Claude Desktop you can also pick them from the
connector's menu under "Add files, connectors, and more"; in Claude Code they are slash commands marked (MCP).

You can ask for one clarifier card per reading. Claude may offer one when the cards in the deciding positions split
evenly, and draws it only if you agree.

## Data

Each draw sends `tarot-reader-omega.vercel.app` the spread's position names and the spread's name. Custom spreads
use short position names written for your situation, such as "What staying costs". The skill tells Claude to keep
your question, names, places and other private details out of them; your conversation itself is never sent. The
server stores nothing, and its host keeps standard request logs. See the
[privacy policy](https://github.com/StephanRyatt/tarot-reader/blob/main/docs/PRIVACY.md).

Readings are for reflection. They are not medical, legal or financial advice.
