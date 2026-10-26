# Privacy

`pc_ping` returns a fixed skeleton message and the optional `note` argument to the calling Dify app. It does not send that note, the Server URL, or the bearer token to PowerContext or any other network service.

Credential validation checks that `server_url` is an `http` or `https` URL and that `api_token` is non-empty. It does not transmit the credential. `scope_id` is kept on the credential for later tools and is not resolved.
