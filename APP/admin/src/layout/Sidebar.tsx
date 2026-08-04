import { NavLink } from 'react-router-dom';
import { SECTION_REGISTRY } from '../sections/_registry';

export function Sidebar() {
  return (
    <aside className="flex w-56 flex-col border-l border-gray-200 bg-white">
      <div className="flex h-14 items-center justify-center border-b border-gray-200">
        <span className="text-lg font-bold text-blue-600">יחדיו ניהול</span>
      </div>

      <nav className="flex-1 overflow-y-auto p-3">
        {SECTION_REGISTRY.map(({ navItem }) => (
          <NavLink
            key={navItem.path}
            to={navItem.path}
            className={({ isActive }) =>
              `flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-blue-50 text-blue-700'
                  : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
              }`
            }
          >
            <navItem.Icon className="h-4 w-4" />
            {navItem.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
