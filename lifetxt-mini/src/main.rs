use std::{env, fs, io};

fn is_supported_task(line: &str, id: &str) -> bool {
    let rest = line.strip_prefix("[ ] T ").or_else(|| line.strip_prefix("[x] T ")).or_else(|| line.strip_prefix("[N] T "));
    rest.map(|value| value.split_whitespace().any(|token| token == format!("id:{id}"))).unwrap_or(false)
}

fn mark_done(input: &str, id: &str) -> io::Result<String> {
    let mut output = String::with_capacity(input.len());
    for segment in input.split_inclusive(|c| c == '\n') {
        let line = segment.trim_end_matches(['\r', '\n']);
        if is_supported_task(line, id) {
            let prefix = match line.as_bytes().get(1) {
                Some(b' ') => "[x]",
                Some(b'x') => "[x]",
                Some(b'N') => "[x]",
                _ => "[x]",
            };
            output.push_str(prefix);
            output.push_str(&line[3..]);
            output.push_str(&segment[line.len()..]);
        } else {
            output.push_str(segment);
        }
    }
    if !input.ends_with('\n') && output.ends_with('\n') { output.pop(); }
    Ok(output)
}

fn main() -> io::Result<()> {
    let args: Vec<String> = env::args().collect();
    if args.len() != 3 || args[1] != "done" {
        eprintln!("usage: lifetxt-mini-preservation-poc done <id> [fixture via stdin is not supported]");
        std::process::exit(2);
    }
    let input = fs::read_to_string("fixtures/mixed-life.txt")?;
    print!("{}", mark_done(&input, &args[2])?);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    const FIXTURE: &str = include_str!("../fixtures/mixed-life.txt");

    #[test]
    fn targeted_edit_only_changes_supported_task_status() {
        let actual = mark_done(FIXTURE, "t1").unwrap();
        let expected = FIXTURE.replace("[ ] T \"Buy milk\" id:t1", "[x] T \"Buy milk\" id:t1");
        assert_eq!(actual, expected);
        assert!(actual.contains("[/] H \"Exercise\" repeat:weekdays custom:x"));
        assert!(actual.contains("[N] J \"Today\" mood:good"));
        assert!(actual.contains("| Some journal text."));
    }
}
