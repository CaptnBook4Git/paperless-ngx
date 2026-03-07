from datetime import date, timedelta

from imap_tools import AND

from paperless_mail.mail import get_mailbox
from paperless_mail.mail import mailbox_login
from paperless_mail.models import MailAccount
from paperless_mail.models import MailRule


def main() -> None:
	account = MailAccount.objects.get(name="icloud")
	rule = MailRule.objects.get(name="rechnung")

	with get_mailbox(account.imap_server, account.imap_port, account.imap_security) as mailbox:
		mailbox_login(mailbox, account)
		mailbox.folder.set(rule.folder)

		criteria = [
			("ALL", "ALL"),
			("UNSEEN", AND(seen=False)),
			("SUBJECT", AND(subject=rule.filter_subject)),
			("SINCE", AND(date_gte=date.today() - timedelta(days=rule.maximum_age))),
			("UNSEEN+SUBJECT", AND(seen=False, subject=rule.filter_subject)),
			(
				"SUBJECT+SINCE",
				AND(
					subject=rule.filter_subject,
					date_gte=date.today() - timedelta(days=rule.maximum_age),
				),
			),
			(
				"UNSEEN+SINCE",
				AND(
					seen=False,
					date_gte=date.today() - timedelta(days=rule.maximum_age),
				),
			),
			(
				"FULL",
				AND(
					seen=False,
					subject=rule.filter_subject,
					date_gte=date.today() - timedelta(days=rule.maximum_age),
				),
			),
		]

		for label, query in criteria:
			count = sum(
				1
				for _ in mailbox.fetch(
					criteria=query,
					mark_seen=False,
					charset=account.character_set,
					bulk=True,
				)
			)
			print(f"{label}: {count}")


main()
