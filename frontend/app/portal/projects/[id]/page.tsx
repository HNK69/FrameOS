import { ClientPortal } from "@/components/client-portal";

export default async function ProjectPortalPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const resolvedParams = await params;
  return <ClientPortal initialProjectId={Number(resolvedParams.id)} />;
}
