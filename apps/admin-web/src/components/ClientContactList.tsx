import type { ClientListItem } from "../types/api";

export function ClientContactList({ client }: { client: ClientListItem }) {
  const contacts = client.contacts ?? [];
  if (!contacts.length) {
    return <div className="client-contact-summary"><strong>{client.contact_name || "—"}</strong>{client.contact_email && <span>{client.contact_email}</span>}</div>;
  }
  return <ul className="client-contact-list" aria-label={`${client.name}の担当者一覧`}>
    {contacts.map((contact) => <li key={contact.id} className="client-contact-summary">
      <div><strong>{contact.name}</strong>{contact.role && <span>（{contact.role}）</span>}{!contact.is_active && <span className="status-badge inactive">無効</span>}</div>
      {contact.phone && <span>電話: {contact.phone}</span>}
      {contact.email && <span>メール: {contact.email}</span>}
    </li>)}
  </ul>;
}
