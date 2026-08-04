export type UserStatus = 'active' | 'suspended' | 'banned';

export interface Profile
{
    user_id:       string;
    name:          string;
    gender:        string;
    date_of_birth: string | null;
    city:          string;
    region:        string;
    bio:           string;
    looking_for:   string;
    status:        UserStatus;
    photo_urls:    string[];
    updated_at:    string;
}

export interface Candidate
{
    user_id:   string;
    name:      string;
    city:      string;
    photo_url: string | null;
    age:       number | null;
}

export interface PeerProfile
{
    user_id:     string;
    name:        string;
    city:        string;
    region:      string;
    bio:         string;
    looking_for: string;
    photo_urls:  string[];
}
