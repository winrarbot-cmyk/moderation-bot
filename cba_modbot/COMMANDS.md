# CBA Moderation Bot – Command Reference

> **Version:** 1.0  
> **Prefix:** `!` (configurable)  
> **Slash commands:** `/report`  
> **Database:** MongoDB via Motor (async)  
> **Framework:** discord.py 2.x, Python 3.12+

---

## Table of Contents

1. [Permission System](#1-permission-system)
2. [Moderation Commands](#2-moderation-commands)
3. [Warning Commands](#3-warning-commands)
4. [Case Management Commands](#4-case-management-commands)
5. [Evidence Commands](#5-evidence-commands)
6. [Queue Punishment Commands](#6-queue-punishment-commands)
7. [Report Commands](#7-report-commands)
8. [Appeal Commands](#8-appeal-commands)
9. [Punishment Escalation Rules](#9-punishment-escalation-rules)
10. [Warning Expiry Rules](#10-warning-expiry-rules)
11. [Escalation Alerts](#11-escalation-alerts)

---

## 1. Permission System

### Staff Roles

The following roles grant access to all staff-only commands. Roles are configured in `config/settings.py` under `staff_roles`.

| Role      | Access Level         |
|-----------|----------------------|
| Owner     | All commands         |
| Admin     | All commands         |
| Moderator | All commands         |

### Regular Users

Regular users (no staff role) may only use:

| Command   | Description              |
|-----------|--------------------------|
| `/report` | Submit a player report   |
| `!appeal` | Submit a punishment appeal |

---

## 2. Moderation Commands

### `!gentimeout`

Apply Discord's native timeout to a user. **No roles are created.**

**Permission:** Staff only  
**Usage:** `!gentimeout @user <duration> [reason]`

**Duration formats:**
- `30m` – 30 minutes
- `2h` – 2 hours
- `24h` – 24 hours
- `7d` – 7 days
- Maximum: `28d` (Discord limit)

**Examples:**

```
!gentimeout @PlayerXYZ 1h Toxic behaviour in queue chat
!gentimeout @PlayerXYZ 24h Discriminatory remarks
```

**Output:**
- Creates a warning record and punishment entry in the database
- Applies Discord's built-in timeout (user cannot send messages or join voice)
- Returns a confirmation embed with case ID, duration, and expiry timestamp

---

## 3. Warning Commands

### `!warn`

Issue a formal warning to a user. Automatically checks for escalation if the reason matches a known infraction.

**Permission:** Staff only  
**Usage:** `!warn @user <reason>`

**Examples:**

```
!warn @PlayerXYZ Queue Dodge
!warn @PlayerXYZ Toxicity in post-match chat
!warn @PlayerXYZ rage quitting
```

**Behaviour:**

1. If the reason **matches** a known infraction exactly, the bot looks up how many prior offences the user has for that reason and recommends the next escalation step.
2. If the reason **does not match** but is close to a known infraction (fuzzy match), the bot asks:
   - ✅ **Confirm Original Reason** – saves as a custom warning
   - ❌ **Use Suggested Reason** – uses the matched official infraction
3. If a punishment (queue lock, queue ban) is recommended, the bot shows:
   - ✅ **Apply** – applies the punishment immediately
   - ❌ **Warning Only** – records only the warning
4. The warning is saved to MongoDB with a unique 5-digit **Case ID**.
5. Automatic punishment expiry is set based on warning type (60 days queue, 90 days community).
6. Community warnings trigger automatic escalation (timeout → kick → ban) based on total active count.

**Stored fields:**

| Field        | Description                              |
|--------------|------------------------------------------|
| case_id      | Unique 5-digit ID                        |
| user_id      | Discord user ID                          |
| mod_id       | Moderator who issued the warning         |
| reason       | Infraction reason                        |
| category     | Queue Infraction / Competitive Integrity / In-Game Behaviour / Community |
| punishment   | Type and label of applied punishment     |
| warning_type | `queue` or `community`                   |
| status       | Open / Under Review / Punished / etc.    |
| active       | Whether the warning is still active      |
| expires_at   | Calculated expiry timestamp              |
| created_at   | Issue timestamp                          |

---

### `!warns`

Display the full moderation record of a user.

**Permission:** Staff only  
**Usage:** `!warns @user`

**Output sections:**
- ⚠️ Queue Warnings (active + expired)
- 💬 Community Warnings (active + expired)
- 🚫 Queue Bans (active + ended)
- ⏱️ Queue Locks
- ⏸️ General Timeouts
- 📨 Appeals

Each entry shows: Case ID, reason, moderator, date, and active/expired status.

If any case has attached evidence, a **📎 View Evidence** button appears. Clicking it shows the evidence in an ephemeral (private) response visible only to the user who clicked.

**Example entry:**
```
#51832 | Queue Dodge | Mod: Kaia | 12/06/2026 | 🟢 Active
```

---

## 4. Case Management Commands

### `!case`

Display full details of a case.

**Permission:** Staff only  
**Usage:** `!case <case_id>`

**Example:**
```
!case 51832
```

**Displayed information:**
- User and moderator
- Reason and category
- Punishment applied
- Date and status
- Notes (internal moderator notes)
- Linked appeal IDs
- All attached evidence

A **status dropdown** is shown allowing the moderator to change the case status:

| Status       | Description                              |
|--------------|------------------------------------------|
| Open         | Default on creation                      |
| Under Review | Being actively investigated              |
| Punished     | Punishment has been applied              |
| Appealed     | User has submitted an appeal             |
| Closed       | Case resolved, no further action         |

---

### `!case note`

Add an internal moderator note to a case.

**Permission:** Staff only  
**Usage:** `!case note <case_id> <note>`

**Example:**
```
!case note 51832 User was given a verbal warning prior to this incident.
```

Notes are stored with the moderator's name and timestamp and are visible only via `!case`.

---

### `!history`

Show all cases associated with a user in chronological order (newest first).

**Permission:** Staff only  
**Usage:** `!history @user`

**Example:**
```
!history @PlayerXYZ
```

Returns up to 20 cases, each showing case ID, reason, punishment, moderator, date, and status icon.

---

## 5. Evidence Commands

### `!evidence add`

Attach evidence to an existing case. Opens an interactive form, then listens for file uploads for 5 minutes.

**Permission:** Staff only  
**Usage:** `!evidence add <case_id>`

**Example:**
```
!evidence add 51832
```

**Process:**
1. A button appears to open the **Evidence Form** (modal).
2. The modal contains:
   - **Evidence Link** – YouTube, Medal, Twitch, Streamable, or any URL
   - **Notes** – description of the evidence
3. After submitting the modal, the bot listens for **5 minutes** for file uploads in the channel.
4. Accepted uploads: images, videos, Discord attachments, any URL in message text.
5. Type `done` to finish early.

**Accepted evidence types:**
- Images (PNG, JPG, GIF, etc.)
- Video files
- Discord attachment links
- YouTube links (`youtube.com`, `youtu.be`)
- Medal clips (`medal.tv`)
- Twitch clips (`twitch.tv`, `clips.twitch.tv`)
- Streamable links (`streamable.com`)
- Any generic `https://` URL

Evidence is stored in the database and accessible via `!warns` and `!case`.

---

### `!evidence delete`

Remove an evidence entry from a case.

**Permission:** Staff only  
**Usage:** `!evidence delete <case_id>`

**Example:**
```
!evidence delete 51832
```

A selection menu appears showing all evidence entries for that case. Select the entry to remove. Deletion is permanent.

---

## 6. Queue Punishment Commands

### `!queueban`

Remove a user's access to all queue-related channels for a specified duration. **No roles are created** – uses Discord channel permission overrides.

**Permission:** Staff only  
**Usage:** `!queueban @user <duration> [reason]`

**Duration formats:** `30m`, `2h`, `7d`, `30d`, `permanent`

**Affected channels** (configured in `config/settings.py`):
- `#queue`
- `#matchmaking`
- `#find-team`
- `#scrims`

**Examples:**
```
!queueban @PlayerXYZ 7d Smurfing
!queueban @PlayerXYZ 30d Account Sharing
!queueban @PlayerXYZ permanent Match Manipulation
```

**Output:**
- Records a warning and queue ban in the database
- Removes `ViewChannel` permission from all queue channels
- Returns a confirmation embed with case ID, duration, and expiry time
- When the ban expires, the background task automatically restores channel access

---

### `!unqueueban`

Manually remove an active queue ban and restore queue channel access.

**Permission:** Staff only  
**Usage:** `!unqueueban @user`

**Example:**
```
!unqueueban @PlayerXYZ
```

**Output:**
- Deactivates the database record
- Restores `ViewChannel` permission in all queue channels (removes the override)

---

## 7. Report Commands

### `/report`

Submit a player report. Opens an interactive modal.

**Permission:** All users  
**Type:** Slash command  
**Usage:** `/report user:@PlayerXYZ`

**Modal fields:**
- **Match ID** – The match identifier (e.g. `CBA-2026-0042`)
- **Description** – Detailed description of the incident
- **Evidence Link** *(optional)* – Any URL

**After submission:**
1. A **5-digit Case ID** is generated.
2. A report embed is posted in `#support-reports` with action buttons for staff.
3. The reporter receives a private confirmation:
   ```
   ✅ Report submitted! Case #51832 has been created.
   You can attach additional evidence using: !evidence add 51832
   ```

**Staff buttons on the report embed:**

| Button            | Action                                           |
|-------------------|--------------------------------------------------|
| ✅ Accept          | Sets status to "Under Review"                   |
| ❌ Reject          | Sets status to "Closed"                         |
| ⚖️ Punish          | Sets status to "Punished" (manual punishment)   |
| 📋 User History   | Shows the reported user's warning history (ephemeral) |

---

### `!reportreview`

Pull up a report for staff review by its case ID.

**Permission:** Staff only  
**Usage:** `!reportreview <case_id>`

**Example:**
```
!reportreview 51832
```

Displays the full report with staff action buttons.

---

## 8. Appeal Commands

### `!appeal`

Submit an appeal for a punishment. Opens an interactive form.

**Permission:** All users (own cases only)  
**Usage:** `!appeal`

**Modal fields:**
- **Case ID** – The 5-digit case number to appeal
- **Reason for Appeal** – Why the punishment should be reconsidered
- **Additional Information** *(optional)* – Witnesses, extra context, evidence

**Restrictions:**
- Users may only appeal cases issued to them.
- Only one pending appeal per case is allowed.

**After submission:**
- The appeal is posted in `#appeals` with staff review buttons.
- The case status is updated to **Appealed**.
- The appellant receives a private confirmation.

---

### `!appealreview`

Pull up an appeal for staff review.

**Permission:** Staff only  
**Usage:** `!appealreview <appeal_id>`

**Example:**
```
!appealreview 74219
```

**Staff action buttons:**

| Button               | Action                                                     |
|----------------------|------------------------------------------------------------|
| ✅ Accept Appeal      | Marks appeal as Accepted; DMs the user                    |
| ❌ Reject Appeal      | Marks appeal as Rejected; DMs the user                    |
| ⬇️ Reduce Punishment  | Marks as Reduced; DMs the user                            |

After selecting an action, a modal appears to add an optional staff review note. The appellant receives a DM with the verdict and note.

---

## 9. Punishment Escalation Rules

The bot tracks prior offences per infraction type and automatically recommends the next escalation tier.

### Queue Infractions

| Infraction                          | 1st        | 2nd          | 3rd (Repeated) | 4th (No Improvement) |
|-------------------------------------|------------|--------------|----------------|----------------------|
| Queue Dodge                         | Warning    | 15m Lock     | 3h Lock        | 12h Lock             |
| Leaving Queue After Accepting       | 15m Lock   | 1h Lock      | 3h Lock        | 12h Lock             |
| Not Showing Up After Teams Chosen   | 1h Lock    | 3h Lock      | 12h Lock       | 1d Lock              |
| Repeated AFK                        | Warning    | 1h Lock      | 3h Lock        | 1d Lock              |
| Intentionally Delaying a Match      | 1h Lock    | 3h Lock      | 12h Lock       | 1d Lock              |
| Refusing to Play Assigned Match     | 3h Lock    | 12h Lock     | 1d Lock        | 7d Lock              |

### Competitive Integrity

| Infraction          | 1st       | 2nd        | 3rd+      |
|---------------------|-----------|------------|-----------|
| Smurfing            | 7d Ban    | 30d Ban    | Perm Ban  |
| Account Sharing     | 7d Ban    | 30d Ban    | Perm Ban  |
| Boosting            | 30d Ban   | Perm Ban   | —         |
| Queue Ban Evasion   | 30d Ban   | Perm Ban   | —         |
| Match Manipulation  | Perm Ban  | —          | —         |

### In-Game Behaviour

| Infraction               | 1st        | 2nd       | 3rd (Repeated) | 4th (No Improvement) |
|--------------------------|------------|-----------|----------------|----------------------|
| Toxicity                 | Warning    | 1h Lock   | 3h Lock        | 1d Lock              |
| Harassment               | 1d Lock    | 7d Lock   | 30d Ban        | Perm Ban             |
| Discriminatory Language  | 7d Ban     | 30d Ban   | Perm Ban       | —                    |
| Threats / Doxxing        | Perm Ban   | —         | —              | —                    |

### Community Warning Escalation

Applied automatically when a user's active community warning count reaches a threshold:

| Active Warnings | Action         |
|-----------------|----------------|
| 1               | Warning        |
| 2               | 1h Timeout     |
| 3               | 24h Timeout    |
| 4               | 7d Timeout     |
| 5               | Kick           |
| 6               | Ban            |

---

## 10. Warning Expiry Rules

| Type               | Expiry         |
|--------------------|----------------|
| Queue Warnings     | 60 days        |
| Community Warnings | 90 days        |
| Smurfing           | Never expires  |
| Account Sharing    | Never expires  |
| Boosting           | Never expires  |
| Match Manipulation | Never expires  |

Expired warnings are automatically marked inactive by a background task that runs every 5 minutes. They remain visible in `!warns` and `!history` under the "Expired" section.

---

## 11. Escalation Alerts

The bot automatically posts alerts to `#moderation-alerts` and pings `@Moderator` when:

| Trigger                            | Threshold                |
|------------------------------------|--------------------------|
| Reports against the same user      | 3 reports within 7 days  |
| Queue Dodges by the same user      | 2 dodges within 24 hours |

Alerts are triggered on every `!warn` and `/report` submission that crosses a threshold. Additional rules can be added in `config/settings.py` under `alert_rules`.

---

## Configuration Reference

All key settings live in `config/settings.py`:

| Key                 | Description                                              |
|---------------------|----------------------------------------------------------|
| `prefix`            | Command prefix (default `!`)                             |
| `staff_roles`       | List of role names with staff access                     |
| `channels.reports`  | Channel name for report embeds                           |
| `channels.appeals`  | Channel name for appeal embeds                           |
| `channels.moderation_alerts` | Channel name for escalation pings               |
| `channels.queue_channels`   | List of queue channel names for ban overrides   |
| `escalation`        | Full escalation tables per infraction                    |
| `community_escalation` | Threshold-based community warning escalation         |
| `expiry_days`       | Warning expiry periods per type                          |
| `alert_rules`       | Escalation alert trigger rules                           |

---

## Quick Reference

| Command               | Who         | Description                              |
|-----------------------|-------------|------------------------------------------|
| `!warn @u reason`     | Staff       | Issue a warning with escalation check    |
| `!warns @u`           | Staff       | View full record of a user               |
| `!history @u`         | Staff       | View all cases for a user                |
| `!case <id>`          | Staff       | View full case details                   |
| `!case note <id> …`   | Staff       | Add internal note to a case              |
| `!evidence add <id>`  | Staff       | Add evidence to a case                   |
| `!evidence delete <id>` | Staff     | Remove evidence from a case              |
| `!queueban @u dur reason` | Staff   | Queue-ban a user                         |
| `!unqueueban @u`      | Staff       | Lift a queue ban                         |
| `!gentimeout @u dur reason` | Staff | Apply a Discord timeout                  |
| `!reportreview <id>`  | Staff       | Review a report by case ID               |
| `!appealreview <id>`  | Staff       | Review an appeal by appeal ID            |
| `/report user:@u`     | All users   | Submit a player report                   |
| `!appeal`             | All users   | Submit a punishment appeal               |
