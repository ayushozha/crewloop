export const metadata = {
  title: "Bay Events Co. — Staffing portal",
};

const SHIFT_DATA = {
  business_name: "Bay Events Co.",
  role: "bartender",
  description: "Urgent bartender replacement for a private product launch. Original contractor canceled 42 minutes ago.",
  location: "SoMa",
  start_time: "Tonight, 6:00 PM",
  end_time: "Tonight, 10:00 PM",
  pay_amount: 120,
  urgency: "urgent",
  required_skills: ["event experience", "bartending", "guest service"],
  source_type: "staffing_portal",
  evidence_summary:
    "Open shift row shows a canceled bartender replacement tonight from 6:00 PM to 10:00 PM in SoMa for $120.",
};

export default function BayEventsStaffingPage() {
  return (
    <div className="min-h-screen" style={{ background: "#F4F1EA", color: "#171511" }}>
      <header className="flex h-[68px] items-center justify-between border-b border-[#DDD5C6] px-9" style={{ background: "rgba(255,254,250,0.82)" }}>
        <div className="text-[20px] font-bold tracking-tight">Bay Events Co.</div>
        <div className="font-mono text-[12px] uppercase tracking-[0.08em] text-[#6E695F]">Staffing portal</div>
      </header>

      <main className="mx-auto max-w-[1120px] px-9 py-9">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-6">
          <div>
            <h1 className="m-0 mb-2 text-[32px] leading-[1.1] tracking-tight">Open staffing needs</h1>
            <p className="m-0 text-[#6E695F]">Tonight&apos;s warehouse and event coverage across San Francisco.</p>
          </div>
          <div className="flex items-center gap-2 font-bold text-[#B94731]">
            <span className="h-[9px] w-[9px] rounded-full bg-[#B94731]" />
            1 urgent replacement
          </div>
        </div>

        <section
          className="overflow-hidden rounded-[18px] border border-[#DDD5C6]"
          style={{ background: "#FFFEFA", boxShadow: "0 18px 50px rgba(23,21,17,0.08)" }}
          aria-label="Open shifts"
        >
          <table className="w-full border-collapse">
            <thead>
              <tr style={{ background: "#FBF8F1" }}>
                {["Shift", "Window", "Location", "Requirements", "Pay", "Status", ""].map((h) => (
                  <th
                    key={h}
                    className="border-b border-[#ECE6DC] px-5 py-[18px] text-left align-top text-[12px] uppercase tracking-[0.09em] text-[#6E695F]"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="border-b border-[#ECE6DC] px-5 py-[18px] align-top">
                  <div className="text-[18px] font-extrabold">Bartender replacement</div>
                  <div className="mt-1 text-[13px] text-[#6E695F]">Original contractor canceled 42 minutes ago.</div>
                </td>
                <td className="border-b border-[#ECE6DC] px-5 py-[18px] align-top">
                  Tonight
                  <br />
                  6:00 PM - 10:00 PM
                </td>
                <td className="border-b border-[#ECE6DC] px-5 py-[18px] align-top">
                  SoMa
                  <br />
                  <span className="text-[13px] text-[#6E695F]">Private product launch</span>
                </td>
                <td className="border-b border-[#ECE6DC] px-5 py-[18px] align-top">
                  {SHIFT_DATA.required_skills.map((skill) => (
                    <span
                      key={skill}
                      className="mb-1.5 mr-1 inline-flex items-center rounded-full px-2 py-1 text-[12px] font-semibold"
                      style={{ background: "#EFEAE0", color: "#4C463C" }}
                    >
                      {skill}
                    </span>
                  ))}
                </td>
                <td className="border-b border-[#ECE6DC] px-5 py-[18px] align-top">
                  <span className="font-extrabold">$120</span>
                </td>
                <td className="border-b border-[#ECE6DC] px-5 py-[18px] align-top">
                  <span
                    className="inline-flex items-center rounded-full px-2 py-1 text-[12px] font-semibold"
                    style={{ background: "#F5E3DC", color: "#B94731" }}
                  >
                    urgent
                  </span>
                </td>
                <td className="border-b border-[#ECE6DC] px-5 py-[18px] align-top">
                  <div className="flex justify-end gap-2">
                    <button
                      className="rounded-[10px] px-3 py-2.5 font-bold"
                      style={{ background: "#EFEAE0", color: "#171511" }}
                    >
                      View
                    </button>
                    <button
                      className="rounded-[10px] px-3 py-2.5 font-bold text-white"
                      style={{ background: "#171511" }}
                    >
                      Fill shift
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </section>

        {/* Embedded JSON for the browser-import demo to scrape. */}
        <script
          id="crewloop-shift-data"
          type="application/json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(SHIFT_DATA) }}
        />
      </main>
    </div>
  );
}
