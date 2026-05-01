import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import ToastContainer from '../ui/Toast'

export default function Layout() {
  return (
    <div className="flex min-h-screen bg-bg-base">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
      <ToastContainer />
    </div>
  )
}
