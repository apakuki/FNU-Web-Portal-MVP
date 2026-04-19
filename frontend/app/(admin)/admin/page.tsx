export default function AdminDashboardPage() {
  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-dark">Admin Dashboard</h1>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[
          { title: "Pending Applications", value: "--" },
          { title: "Active Students", value: "--" },
          { title: "Outstanding Fees", value: "--" },
        ].map((stat) => (
          <div
            key={stat.title}
            className="rounded-lg border bg-white p-6 shadow-sm"
          >
            <p className="text-sm text-gray">{stat.title}</p>
            <p className="mt-1 text-2xl font-bold text-dark">{stat.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
