export function PagePlaceholder({ title, note }: { title: string; note: string }) {
  return (
    <div>
      <h1 className="text-xl font-semibold">{title}</h1>
      <p className="mt-2 text-sm text-slate-500">{note}</p>
    </div>
  );
}
