export default function ResearchLoading() {
  return (
    <main className="min-h-screen bg-[#f4f0e8] px-5 py-16 text-[#17201d]">
      <div className="mx-auto max-w-7xl animate-pulse" aria-label="Loading research evidence">
        <div className="h-4 w-48 rounded bg-[#d9d3c6]" />
        <div className="mt-5 h-14 max-w-3xl rounded bg-[#ded8cc]" />
        <div className="mt-12 grid gap-4 md:grid-cols-3">
          {[0, 1, 2].map((item) => (
            <div key={item} className="h-36 rounded-2xl bg-[#e5dfd3]" />
          ))}
        </div>
      </div>
    </main>
  );
}
