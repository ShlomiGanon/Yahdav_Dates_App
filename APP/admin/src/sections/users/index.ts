import { createElement } from 'react';
import { UserListPage } from './UserListPage';
import { UserDetailPage } from './UserDetailPage';

function UsersIcon({ className }: { className?: string }) {
  return createElement(
    'svg',
    {
      className,
      xmlns: 'http://www.w3.org/2000/svg',
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: 'currentColor',
      strokeWidth: '2',
      strokeLinecap: 'round',
      strokeLinejoin: 'round',
    },
    createElement('path', { d: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2' }),
    createElement('circle', { cx: '9', cy: '7', r: '4' }),
    createElement('path', { d: 'M23 21v-2a4 4 0 0 0-3-3.87' }),
    createElement('path', { d: 'M16 3.13a4 4 0 0 1 0 7.75' }),
  );
}

export const usersSection = {
  navItem: { label: 'משתמשים', Icon: UsersIcon, path: '/admin/users' },
  route: {
    path: 'users',
    children: [
      { index: true, element: createElement(UserListPage) },
      { path: ':id',  element: createElement(UserDetailPage) },
    ],
  },
};
