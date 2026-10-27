    # SigmaOS-greeter

    Slick login greeter with user list & a11y

    Part of the **SigmaOS** sovereign operating-system ecosystem — a multi-repository
    distribution modelled on Linux Mint and Omarchy Linux. See the parent
    [`SigmaOS`](https://github.com/AaryanSinghChauhan09/SigmaOS) repository for the
    full component index.

    ## Upstream inspirations
    - https://github.com/linuxmint/slick-greeter

    ## Design principles applied
    - **Secure Defaults**
- **Fail-Fast**
- **Pure Plan / Thin Execute**
- **KISS**
- **Deterministic Testing**

    ## Usage
    Verbs: `users, theme, a11y, launch-plan`

    ```
    $ sigma-greeter users passwd.txt --min-uid 1000
$ sigma-greeter theme sigma-dark
$ sigma-greeter a11y a11y.json
$ sigma-greeter launch-plan --theme sigma-dark --session wayland

    ```

    ## Build & test
    ```
    make build
    make test
    ```

    ## Licence
    GNU General Public License v3.0 (FOSS).
