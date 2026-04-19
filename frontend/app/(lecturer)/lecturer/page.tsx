export default function LecturerDashboardPage() {
  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-fnu-blue">
        Lecturer Dashboard
      </h1>
      <div className="grid gap-4 sm:grid-cols-2">
        {[
          { title: "My Courses", value: "--" },
          { title: "Pending Grades", value: "--" },
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
