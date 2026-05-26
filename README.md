# Draft Notifications

Configurable draft document email notifications for Frappe.

## What It Does

Draft Notifications sends email when a new draft document is created. A draft is any document with
`docstatus = 0`.

Rules are configured with the `Draft Notification Rule` DocType. When a matching document is inserted,
the app creates a Desk notification, an `Email Queue` record, and a `Draft Notification Log` record.
Frappe's email queue sends the email, and the app's scheduler syncs queued log rows to `Sent` or
`Failed`.

## Rule Setup

Create a `Draft Notification Rule` with:

- `Document Type`: target DocType to watch.
- `Recipient Type`: where recipients come from.
- `Subject`: optional Jinja template.
- `Message`: optional Jinja template.
- `Respect Document Read Permission`: skip users who cannot read the document.
- `Include Owner`: also notify the document owner.
- `Do Not Send Twice For Same Document And User`: skip when a queued or sent log already exists.

The Desk notification appears in the bell notification dropdown as a Frappe `Notification Log` with
type `Alert`. Alert notifications do not trigger Frappe's separate notification email, so users only
receive the email created by this app.

Supported recipient types:

- `Fixed Users`: users from the child table.
- `Users With Role`: all users assigned to the selected role.
- `User Field`: a field on the target document that stores a User id.
- `Owner`: the target document owner.
- `Custom Method`: a Python dotted path that receives the document and returns a user or list of users.

## Templates

`Subject` and `Message` use Frappe/Jinja templates.

Available variables:

- `doc`: the draft document.
- `doc_url`: the Desk form URL for the draft document.

Example subject:

```jinja
New draft {{ doc.doctype }} {{ doc.name }}
```

Example message:

```jinja
<p>A new draft {{ doc.doctype }} has been created: <a href="{{ doc_url }}">{{ doc.name }}</a></p>
```

## Custom Methods

Custom methods must point to installed app modules and cannot point to private modules or methods.

By default, allowed prefixes are derived from installed app names, excluding `frappe`, for example:

```text
erpnext.
draft_notifications.
```

You can override the allowed prefixes in `site_config.json`:

```json
{
  "draft_notification_allowed_method_prefixes": ["crm_integration.", "draft_notifications."]
}
```

Example method:

```python
def get_draft_notification_users(doc):
	return [doc.owner]
```

## Log Statuses

- `Queued`: an Email Queue record exists and is waiting for Frappe's email sender.
- `Sent`: the Email Queue record was sent successfully.
- `Skipped`: the recipient was skipped, usually because of missing email, permissions, or deduplication.
- `Failed`: email queueing or sending failed.

## Retry Failed Logs

Failed logs are not retried automatically. This avoids repeated emails when SMTP or configuration is
broken.

You can retry one failed log:

```python
frappe.call(
	"draft_notifications.draft_notifications.draft_notification.retry_failed_log",
	log_name="DRAFT-NOTIFY-2026-00001",
)
```

You can retry a batch:

```python
frappe.call(
	"draft_notifications.draft_notifications.draft_notification.retry_failed_logs",
	limit=100,
)
```

Retries create a new `Draft Notification Log` row and a new `Email Queue` row.
