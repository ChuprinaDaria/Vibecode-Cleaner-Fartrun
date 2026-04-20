# Nagger System

The nagger is fartrun's notification escalation system. When your code health drops, the nagger makes sure you know about it — politely at first, then less so.

## Escalation Levels

The nagger has 4 levels, triggered by health score thresholds. Messages are available in English (EN) and Ukrainian (UA).

### Level 1: Gentle Nudge (Score 60-79)

Low-key reminders. One notification per scan.

| EN | UA |
|----|-----|
| "Your code could use some love." | "Твій код потребує трохи уваги." |
| "A few things worth looking at." | "Є кілька речей, на які варто глянути." |
| "Not bad, but not great either." | "Не погано, але й не супер." |

### Level 2: Firm Warning (Score 40-59)

More insistent. Notification + sound.

| EN | UA |
|----|-----|
| "Okay, this is getting messy." | "Окей, тут вже бардак починається." |
| "Your future self will hate you for this." | "Твоє майбутнє я тебе за це зненавидить." |
| "Tech debt is not a personality trait." | "Технічний борг — це не риса характеру." |

### Level 3: Loud Alarm (Score 20-39)

Persistent notifications. Louder sounds. Optional Hasselhoff intervention.

| EN | UA |
|----|-----|
| "This codebase is a cry for help." | "Цей код — крик про допомогу." |
| "I've seen production incidents start this way." | "Я бачив, як з такого починались інциденти на проді." |
| "Do you even test, bro?" | "Ти взагалі тестуєш, братику?" |

### Level 4: Critical (Score 0-19)

Maximum urgency. All notification channels fire. Fart sounds at max volume.

| EN | UA |
|----|-----|
| "Stop. Stop coding. Fix this first." | "Стій. Стій кодити. Спочатку полагодь це." |
| "This is fine. (It's not fine.)" | "Все добре. (Ні, не добре.)" |
| "Your code has achieved sentience and it's angry." | "Твій код став розумним і він злий." |

## Hasselhoff Mode

When `sounds.hasselhoff = true` in config, level 3 and 4 alerts trigger David Hasselhoff motivational content instead of standard notifications.

### Songs

Three songs are available, selected automatically based on context or manually via config:

#### "Looking for Freedom" (1989)
Plays when the codebase needs liberation from technical debt. Default for level 3 alerts.

Used when: dead code percentage > 20%, tech debt score is the worst phase, circular dependencies detected.

#### "True Survivor" (2015)
Plays during rollback operations and when you're recovering from a bad AI refactor. Default for level 4 alerts.

Used when: rollback is performed, security scan finds high-severity issues, test coverage below 20%.

#### "Du" (2004)
Plays for users with German locale or when explicitly selected. The most intense motivational experience.

Used when: `hasselhoff_song = "du"` in config, or system locale starts with `de_`.

### Song Selection Logic

```
if config.hasselhoff_song != "auto":
    play(config.hasselhoff_song)
elif locale.startswith("de_"):
    play("du")
elif rollback_in_progress:
    play("survivor")
else:
    play("freedom")
```

Songs play a 15-second clip, not the full track. The GUI shows an animated Hasselhoff during playback.

## Fart Sounds

The core audio feedback system. Two modes available.

### Gentle Mode (`fart_mode = "gentle"`)

Subtle, short sounds. Suitable for open offices and shared spaces.

- Low-pitched, soft puff sound for level 1
- Quick double-puff for level 2
- Extended whoopee cushion for level 3
- Sad trombone for level 4

### Loud Mode (`fart_mode = "loud"`)

Full-volume, unmistakable sounds. For home offices and people who want maximum awareness.

- Standard whoopee cushion for level 1
- Extended resonant blast for level 2
- Rapid-fire sequence for level 3
- Air horn + extended blast combo for level 4

## Platform Audio Players

Fartrun auto-detects the available audio player:

| OS | Player Priority |
|----|----------------|
| Linux | `paplay` (PulseAudio) > `aplay` (ALSA) > `mpv` > `ffplay` |
| macOS | `afplay` (built-in, always available) |
| Windows | `powershell -c (New-Object Media.SoundPlayer ...)` > `wmplayer` |

If no audio player is found, sounds are silently skipped and a warning is logged.

Audio files are bundled as WAV format inside the package. The binary distribution includes them embedded in the executable.

## Configuration

```toml
[sounds]
enabled = true            # master switch
volume = 0.7              # 0.0 to 1.0
fart_mode = "gentle"      # "gentle" or "loud"
hasselhoff = false         # enable Hasselhoff mode

[alerts]
min_severity = "medium"    # minimum severity to trigger nagger
desktop_notifications = true
sound_on_high = true       # sound only on high severity
```

## Disabling the Nagger

```toml
[sounds]
enabled = false

[alerts]
desktop_notifications = false
```

Or set `min_severity = "high"` to only get nagged about critical issues.

## Adding Custom Sounds

Place WAV files in the data directory:

```
~/.local/share/fartrun/sounds/
    level1.wav
    level2.wav
    level3.wav
    level4.wav
```

Custom sounds override the built-in ones. File names must match exactly.
