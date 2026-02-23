import { Outlet } from 'react-router';
import { AppSidebar } from './components/AppSidebar';

export default function Root() {
  return (
    <div className="w-full h-screen flex bg-[#F7F7F7]">
      <AppSidebar />
      <Outlet />
    </div>
  );
}
