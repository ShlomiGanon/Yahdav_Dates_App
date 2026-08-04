export type UserStatus = 'active' | 'suspended' | 'banned';
export type Gender = 'male' | 'female' | 'other';

export interface Profile
{
    user_id:       string;
    name:          string;
    bio:           string;
    gender:        Gender | null;
    date_of_birth: string | null;
    city:          string;
    region:        string;
    photo_url:     string | null;
}

export interface Candidate
{
    user_id:       string;
    name:          string;
    gender:        Gender | null;
    date_of_birth: string | null;
    city:          string;
    photo_url:     string | null;
}

export interface PeerProfile
{
    user_id:          string;
    name:             string;
    gender:           Gender | null;
    date_of_birth:    string | null;
    city:             string;
    region:           string;
    bio:              string;
    photo_url:        string | null;
    has_extra_photos: boolean;
}

export interface Photo
{
    photo_id: string;
    url:      string;
}
