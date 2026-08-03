import bcrypt from 'bcrypt';
import { v4 as uuidv4 } from 'uuid';
import { authQueries } from '../database/queries/auth.queries';
import { profileQueries } from '../database/queries/profile.queries';

const SALT_ROUNDS = 12;

export interface RegisterInput {
  username: string;
  email: string;
  password: string;
  name: string;
  gender: string;
  date_of_birth: string;
  city: string;
  region: string;
}

export const UserModel = {
  async register(input: RegisterInput): Promise<string> {
    const now = new Date().toISOString();
    const userId = uuidv4();
    const passwordHash = await bcrypt.hash(input.password, SALT_ROUNDS);

    profileQueries.create({
      user_id: userId,
      name: input.name,
      city: input.city,
      region: input.region,
      gender: input.gender,
      date_of_birth: input.date_of_birth,
      registered_at: now,
      updated_at: now,
    });

    authQueries.createCredentials({
      user_id: userId,
      username: input.username,
      email: input.email,
      password_hash: passwordHash,
      created_at: now,
    });

    return userId;
  },

  async verifyPassword(storedHash: string, candidate: string): Promise<boolean> {
    return bcrypt.compare(candidate, storedHash);
  },

  touchLastLogin(userId: string): void {
    authQueries.updateLastLogin(userId, new Date().toISOString());
  },
};
