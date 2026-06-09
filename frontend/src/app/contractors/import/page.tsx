import { PasswordGate } from "@/components/PasswordGate";

import { ImportClient } from "./ImportClient";

export const metadata = {
  title: "Import roster · CrewLoop",
};

export default function ContractorsImportPage() {
  return (
    <PasswordGate>
      <ImportClient />
    </PasswordGate>
  );
}
