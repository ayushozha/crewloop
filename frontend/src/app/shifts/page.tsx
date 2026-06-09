import { PasswordGate } from "@/components/PasswordGate";

import { ShiftsClient } from "./ShiftsClient";

export const metadata = {
  title: "Shifts · CrewLoop",
};

export default function ShiftsPage() {
  return (
    <PasswordGate>
      <ShiftsClient />
    </PasswordGate>
  );
}
