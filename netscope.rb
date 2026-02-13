# Homebrew formula for NetScope CLI
# After PyPI release: get SHA256 with:
#   curl -sL https://pypi.org/packages/source/n/netscope-cli/netscope-cli-1.0.0.tar.gz | shasum -a 256
# Then: brew install --build-from-source ./netscope.rb
# Or tap: brew tap yourusername/netscope && brew install netscope

class Netscope < Formula
  include Language::Python::Virtualenv

  desc "Comprehensive network diagnostics, testing, and security audit tool"
  homepage "https://github.com/netscope-tool/netscope-cli"
  url "https://files.pythonhosted.org/packages/source/n/netscope-cli/netscope-cli-1.0.0.tar.gz"
  sha256 ""  # REQUIRED: Replace with actual SHA256 after first PyPI release
  license "MIT"
  head "https://github.com/netscope-tool/netscope-cli.git", branch: "main"

  depends_on "python@3.11"
  depends_on "nmap" => :recommended

  def install
    venv = virtualenv_create(libexec, "python3.11")
    venv.pip_install buildpath
    (bin/"netscope").write_env_script(libexec/"bin/netscope", PATH: "#{libexec}/bin:$PATH")
  end

  test do
    system "#{bin}/netscope", "--version"
    system "#{bin}/netscope", "--help"
  end
end
