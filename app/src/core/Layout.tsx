import { ReactNode, Suspense, lazy, useEffect } from "react";
import { useAppSettings } from "./AppSettingsContext";
import Breadcrumb from "./Breadcrumb";
import { useFeature } from "./FeatureContext";
import Header from "./Header";
import ImpersonationBanner from "./ImpersonationBanner";
import Sidebar from "./Sidebar";

const MFASetupBanner = lazy(() => import("./mfa/MFASetupBanner"));
const AnnouncementBanner = lazy(
  () => import("./announcement/AnnouncementBanner"),
);
const AnnouncementBlocker = lazy(
  () => import("./announcement/AnnouncementBlocker"),
);
const MaintenanceAdminBanner = lazy(
  () => import("./maintenance_mode/MaintenanceAdminBanner"),
);

interface BreadcrumbItem {
  label: string;
  path?: string;
}

interface Props {
  children: ReactNode;
  breadcrumb?: BreadcrumbItem[];
  fullWidth?: boolean;
  title?: string;
}

export default function Layout({
  children,
  breadcrumb,
  fullWidth,
  title,
}: Props) {
  const { isActive } = useFeature();
  const { settings: appSettings } = useAppSettings();

  useEffect(() => {
    const appTitle = appSettings.app_name || "Sitter";
    document.title = title ? `${title} | ${appTitle}` : appTitle;
    return () => {
      document.title = appTitle;
    };
  }, [title, appSettings.app_name]);

  return (
    <div className="layout">
      <a href="#main-content" className="skip-nav">
        Aller au contenu principal
      </a>
      <Header />
      <ImpersonationBanner />
      {isActive("maintenance_mode") && (
        <Suspense fallback={null}>
          <MaintenanceAdminBanner />
        </Suspense>
      )}
      {isActive("mfa") && (
        <Suspense fallback={null}>
          <MFASetupBanner />
        </Suspense>
      )}
      {isActive("announcement") && (
        <Suspense fallback={null}>
          <AnnouncementBanner />
        </Suspense>
      )}
      {isActive("announcement") && (
        <Suspense fallback={null}>
          <AnnouncementBlocker />
        </Suspense>
      )}
      <div className="layout-body">
        <Sidebar />
        <main
          id="main-content"
          className={`main-content page-enter${fullWidth ? " main-content-full" : ""}`}
        >
          {breadcrumb && breadcrumb.length > 0 && (
            <Breadcrumb items={breadcrumb} />
          )}
          {children}
        </main>
      </div>
    </div>
  );
}
