import { usersSection } from './users';
import type { ComponentType } from 'react';
import type { RouteObject } from 'react-router-dom';

export interface SectionEntry {
  navItem: {
    label: string;
    Icon: ComponentType<{ className?: string }>;
    path: string;
  };
  route: RouteObject;
}

export const SECTION_REGISTRY: SectionEntry[] = [
  usersSection,
  // Add new sections here — no other files need changing
];
