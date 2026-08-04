export type AuthStackParams = {
  Welcome:  undefined;
  Login:    undefined;
  Signup:   undefined;
};

export type MainStackParams = {
  Menu:             undefined;
  Profile:          undefined;
  AdditionalPhotos: undefined;
  Discover:         undefined;
  PeerProfile:      { peer_id: string };
  PeerPhotos:       { peer_id: string };
  ChatHistory:      undefined;
  Chat:             { peer_id: string; peer_name: string };
};
