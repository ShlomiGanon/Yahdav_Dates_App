export type Profile = {
  name:          string;
  bio:           string;
  gender:        string | null;
  date_of_birth: string | null;
  city:          string;
  region:        string | null;
  photo_url:     string | null;
};

export type Photo = {
  photo_id: string;
  url:      string;
};

export type Candidate = {
  user_id:       string;
  name:          string;
  gender:        string | null;
  date_of_birth: string | null;
  city:          string;
  photo_url:     string | null;
};

export type PeerProfile = {
  user_id:          string;
  name:             string;
  gender:           string | null;
  date_of_birth:    string | null;
  city:             string;
  region:           string | null;
  bio:              string;
  photo_url:        string | null;
  has_extra_photos: boolean;
};
