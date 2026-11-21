use std::ffi::OsString;

use tauri::Url;

const USAGE: &str = "Use --server-url followed by the HTTP or HTTPS address of your lifetxt server.\n\n\
                     Example: --server-url http://192.168.1.20:8765/\n\n\
                     Enter the address without a username or password.";

pub fn parse(mut args: impl Iterator<Item = OsString>) -> Result<Option<Url>, &'static str> {
    let Some(option) = args.next() else {
        return Ok(None);
    };
    if option != "--server-url" {
        return Err(USAGE);
    }
    let address = args
        .next()
        .and_then(|arg| arg.into_string().ok())
        .ok_or(USAGE)?;
    if args.next().is_some() || address.contains(['\\', '\n', '\r', '\t']) {
        return Err(USAGE);
    }

    let (scheme, remainder) = address.split_once("://").ok_or(USAGE)?;
    let authority = remainder.split(['/', '?', '#']).next().unwrap_or_default();
    if authority.is_empty() || authority.contains('@') || address.trim() != address {
        return Err(USAGE);
    }
    if !scheme.eq_ignore_ascii_case("http") && !scheme.eq_ignore_ascii_case("https") {
        return Err(USAGE);
    }

    let url = Url::parse(&address).map_err(|_| USAGE)?;
    Ok(Some(url))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse_args(args: &[&str]) -> Result<Option<Url>, &'static str> {
        parse(args.iter().copied().map(OsString::from))
    }

    #[test]
    fn no_option_starts_local_companion() {
        assert_eq!(parse_args(&[]), Ok(None));
    }

    #[test]
    fn supports_lan_vpn_and_https_addresses() {
        for address in [
            "http://192.168.1.20:8765/",
            "http://[fd00::1]:8765/",
            "https://lifetxt.example.com/?mode=display",
        ] {
            let url = parse_args(&["--server-url", address]).unwrap().unwrap();
            assert_eq!(url.as_str(), address);
        }
    }

    #[test]
    fn rejects_invalid_arguments_without_falling_back_to_local() {
        assert!(parse_args(&["--server-url"]).is_err());
        assert!(parse_args(&["--unknown"]).is_err());
        assert!(parse_args(&["--server-url", "http://server/", "extra"]).is_err());
        for address in [
            "server:8765",
            "http:///server",
            "http://",
            "http://server:65536",
            "https://user:password@server/",
            "https://@server/",
            "file:///tmp/life.txt",
            "https://ser\tver/",
            " https://server/",
        ] {
            assert!(parse_args(&["--server-url", address]).is_err());
        }
    }
}
