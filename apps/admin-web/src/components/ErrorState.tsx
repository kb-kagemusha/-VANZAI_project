export function ErrorState({ title, description }: { title: string; description: string }) {
  return (
    <div className="error-state">
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}